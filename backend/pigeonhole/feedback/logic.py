import logging
import os

from courses.models import (Course, CourseMembership, CourseMilestone,
                            CourseMilestoneTemplate, CourseSubmission)
from django.db import transaction
from django.conf import settings
from openai import OpenAI
import pandas as pd
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from pigeonhole.common.constants import COURSE, CREATOR, ID, INITIAL_RESPONSE, MILESTONE, NAME, QUESTION, GENRE, MECHANIC
from pigeonhole.common.parsers import to_base_json
from users.logic import user_to_json
from users.models import User

from .models import FeedbackInitialResponse

logger = logging.getLogger("main")

## TODO: this is only a temporary implemention. Should not rely on webscraping in the long run.
def answer_reflection(driver, element_class, reflection):
    text_questions = driver.find_element(By.CLASS_NAME, element_class)
    text_questions.clear()
    text_questions.send_keys(reflection)

    return driver


def submit(driver, element_class):
    driver.find_element(By.CLASS_NAME, element_class).click()
    return driver


def get_result(driver, element_class):
    result = driver.find_element(By.CLASS_NAME, element_class).get_attribute("value")
    return result


# Returns a two element array of string containing HTML code
# First element contains the HTML of inline annotated reflection
# Segments of text to be highlighted are enclosed by <span> tags with the type of highlight found within the span's class.
# Classes of highlights include context, challenge, affect, modall, epistemic, link2me, change, metrics

# Second element contains the HTML of feedback for the student, provided in a two panel view


def analyse(text):

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    text_question_element_class = "ql-editor"
    submit_element_class = "btn-lg"

    url = "https://acawriter-demo.utscic.edu.au/demo"
    coreDriver = webdriver.Chrome(options=chrome_options)
    coreDriver.get(url)

    select_element = coreDriver.find_element(By.ID, "grammar")
    select_object = Select(select_element)
    select_object.select_by_visible_text("Pharmacy")
    driver = answer_reflection(coreDriver, text_question_element_class, text)
    driver = submit(driver, submit_element_class)
    element = WebDriverWait(driver=driver, timeout=60).until(
        EC.invisibility_of_element((By.CLASS_NAME, "nprogress-busy"))
    )

    element = driver.find_element(
        By.XPATH, "//div[contains(@class, 'col-md-12 wrapper')]"
    )
    results = []
    inlineFeedback = element.get_attribute("innerHTML")

    results.append(inlineFeedback)  # Inline text feedback

    element = driver.find_element(By.ID, "feedback")
    panelFeedback = element.get_attribute("innerHTML")

    # Changing name of analyser
    panelFeedback = panelFeedback.replace("AcaWriter", "Reflection Analyser")

    # Removing ineffective feedback
    panelFeedback = panelFeedback.replace(
        """<li class="col-md-12 p-2"><span class="text-danger"> While it appears that you’ve reported on how you would change/prepare for the future, you don’t seem to have reported first on what you found challenging. Perhaps you’ve reflected only on the positive aspects in your report?. </span></li>""",
        "",
    )
    results.append(panelFeedback)  # Panel text feedback

    coreDriver.close()
    return results


# Returns response from ChatGPT in a single string, which might contain newlines.
# Uses a basic prompt
def askChatGPTOriginal(text):

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Text prompt to generate feedback for the given reflection text
    prompt = "You are an educator with 30 years of education experience in guiding students through reflective learning." + \
            "Use the following step-by-step instructions to grade the given reflection and give feedback directed to the student:" +\
            "Step 1) Analyse and grade the reflection by each stage of reflection using the following reflective writing assessment rubrics. Each section is worth up to 2 marks. A score of 2 should only be given with sufficient details and elaboration from the student." + \
            "<Rubrics Start>" + \
            "Rubrics:" + \
            "Stage 1. Returning to Experience: Statement provides description of the task chronologically and is clear of any judgements" + \
            "Stage 2. Attending to Feelings: Statement conveys personal feelings, thoughts (positive and or negative) of the experience and relates to future personal learning" + \
            "Stage 3. Integration: Statement clearly provides evidence of integration of prior knowledge, feelings, or attitudes with new knowledge, feelings, or attitudes, thus arriving at new perspectives." + \
            "Stage 4. Appropriation: Statement clearly shows evidence that inferences have been made using their own prior knowledge and previous experience throughout the task" + \
            "Stage 5. Outcomes of Reflection: Statement clearly shows evidence of reflection and clearly states: (1) a change in behaviour or development of new perspectives as a result of the task; (2) ability to reflect on own task, apply new knowledge feelings, thoughts, opinions to enhance new future experiences; and (3) examples" + \
            "Additional Stage. Readability and Accuracy: Clear, engaging, accurate and comprehensive text." + \
            "<Rubrics End>" + \
            "Step 2) Display the results by each grading category. For each category, briefly explain what was done well, and if a full score of 2 was not obtained, add some suggestions on how to improve to get a better score." + \
            "Step 3) Tally the overall grade and give an overall summary."

    query = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": prompt
            },
            {
                "role": "user", 
                "content": text
            }],
        temperature=0.1
    )
  
    response = query.choices[0].message.content 

    # Log usage
    logger.info(query.usage) 

    return response 


# Returns response from ChatGPT in a single string, which might contain newlines.
# Uses advanced prompt engineering techniques
def askChatGPT(text):

    scores = askChatGPTForScore(text)
    response = askChatGPTForFeedback(text, scores)
    formatted_response = formatResponse(response)    

    return formatted_response 

class Grade(BaseModel):
    stage_1_score: int
    stage_2_score: int
    stage_3_score: int
    stage_4_score: int
    stage_5_score: int
    additional_stage_score: int

def askChatGPTForScore(text):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Text prompt to generate scores for the given reflection text
    file_path = os.path.join(settings.BASE_DIR, "feedback/prompts/prompt_for_scores.txt")
    f = open(file_path, "r")
    prompt = f.read()
    f.close()

    df = pd.DataFrame(columns=['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4', 'Stage 5', 'Additional Stage'])

    for i in range(3):
        query = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": prompt
                },
                {
                    "role": "user", 
                    "content": text
                }],
            temperature=1,
            response_format=Grade
        )
        response = query.choices[0].message.parsed
        new_row = {'Stage 1': response.stage_1_score, 
                    'Stage 2': response.stage_2_score, 
                    'Stage 3': response.stage_3_score, 
                    'Stage 4': response.stage_4_score,
                    'Stage 5': response.stage_5_score,
                    'Additional Stage': response.additional_stage_score}
        df = df._append(new_row, ignore_index=True)

        # Log usage
        logger.info(query.usage)


    return df.mean(axis=0).tolist()

class Stage(BaseModel):
    score: float
    what_was_done_well: str
    improvement: str

class Feedback(BaseModel):
    stage_1: Stage
    stage_2: Stage
    stage_3: Stage
    stage_4: Stage
    stage_5: Stage
    additional_stage: Stage
    overall_feedback: str

def askChatGPTForFeedback(text, scores):
    scores = [int(val) if val.is_integer() else round(val, 2) for val in scores]
    scores_string = 'Stage 1: {}, Stage 2: {}, Stage 3: {}, Stage 4: {}, Stage 5: {}, Additional Stage {}'
    full_text = text + '\n\n' + scores_string.format(*scores)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Text prompt to generate feedback for the given reflection text
    file_path = os.path.join(settings.BASE_DIR, "feedback/prompts/prompt_for_feedback.txt")
    f = open(file_path, "r")
    prompt = f.read()
    f.close()

    query = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": prompt
            },
            {
                "role": "user", 
                "content": full_text
            }],
        temperature=1,
        response_format=Feedback
    )
  
    response = query.choices[0].message.parsed

    # Log usage
    logger.info(query.usage)

    return response 

def formatResponse(response):
    total_score = response.stage_1.score + response.stage_2.score + response.stage_3.score +\
                    response.stage_4.score + response.stage_5.score + response.additional_stage.score
    if total_score.is_integer():
        total_score = int(total_score)
    cleaned_response = cleanUpResponse(response)

    return "**Stage 1. Returning to Experience: {} / 2** \n".format(cleaned_response.stage_1.score) +\
            "- **What was done well:** {} \n".format(cleaned_response.stage_1.what_was_done_well) +\
            "- **Improvement:** {} \n".format(cleaned_response.stage_1.improvement) +\
            " \n" +\
            "**Stage 2. Attending to Feelings: {} / 2** \n".format(cleaned_response.stage_2.score) +\
            "- **What was done well:** {} \n".format(cleaned_response.stage_2.what_was_done_well) +\
            "- **Improvement:** {} \n".format(cleaned_response.stage_2.improvement) +\
            " \n" +\
            "**Stage 3. Integration: {} / 2** \n".format(cleaned_response.stage_3.score) +\
            "- **What was done well:** {} \n".format(cleaned_response.stage_3.what_was_done_well) +\
            "- **Improvement:** {} \n".format(cleaned_response.stage_3.improvement) +\
            " \n" +\
            "**Stage 4. Appropriation: {} / 2** \n".format(cleaned_response.stage_4.score) +\
            "- **What was done well:** {} \n".format(cleaned_response.stage_4.what_was_done_well) +\
            "- **Improvement:** {} \n".format(cleaned_response.stage_4.improvement) +\
            " \n" +\
            "**Stage 5. Outcomes of Reflection: {} / 2** \n".format(cleaned_response.stage_5.score) +\
            "- **What was done well:** {} \n".format(cleaned_response.stage_5.what_was_done_well) +\
            "- **Improvement:** {} \n".format(cleaned_response.stage_5.improvement) +\
            " \n" +\
            "**Additional Stage. Readability and Accuracy: {} / 2** \n".format(cleaned_response.additional_stage.score) +\
            "- **What was done well:** {} \n".format(cleaned_response.additional_stage.what_was_done_well) +\
            "- **Improvement:** {} \n".format(cleaned_response.additional_stage.improvement) +\
            " \n" +\
            "**Total Score: {} / 12** \n".format(total_score) +\
            "**Summary:** {} \n".format(cleaned_response.overall_feedback)

def cleanUpStage(stage):
    if stage.score.is_integer():
        stage.score = int(stage.score) 
    if stage.score == 2:
        stage.improvement = "No improvement needed. You've done a great job!"
    return stage

def cleanUpResponse(response):
    response.stage_1 = cleanUpStage(response.stage_1)
    response.stage_2 = cleanUpStage(response.stage_2)
    response.stage_3 = cleanUpStage(response.stage_3)
    response.stage_4 = cleanUpStage(response.stage_4)
    response.stage_5 = cleanUpStage(response.stage_5)
    response.additional_stage = cleanUpStage(response.additional_stage)
    return response

@transaction.atomic
def createFeedbackInitialResponseIfNotExists(
    submission_id: int,
    requester: User,
    question: str,
    initial_response: str,
    genre: str | None = None,
    mechanic: str | None = None,
) -> tuple[FeedbackInitialResponse, bool]:
    
    try:
        submission = CourseSubmission.objects.select_related(
            "course",
            "milestone",
            "template"
        ).get(id=submission_id)

    except CourseSubmission.DoesNotExist as e:
        logger.warning(e)
        raise ValueError(f"No such submission found.")
    
    try:
        requester_membership = submission.course.coursemembership_set.get(user=requester)

    except CourseMembership.DoesNotExist as e:
        logger.warning(e)
        raise ValueError(f"No such user found in given course.")

    # Create new record only if none exists already
    new_initial_response, created = FeedbackInitialResponse.objects.get_or_create(
        course=submission.course,
        milestone=submission.milestone,
        template=submission.template,
        creator=requester_membership,
        question=question,
        defaults={
            "name": submission.template.__str__(), 
            "initial_response":initial_response,
            "genre":initial_response,
            "mechanic":initial_response,
        }
    )

    return new_initial_response, created

def feedback_initial_response_to_json(response: FeedbackInitialResponse) -> dict:
    data = to_base_json(response)

    data |= {
        NAME: response.name,
        QUESTION: response.question,
        INITIAL_RESPONSE: response.initial_response,
        GENRE: response.genre,
        MECHANIC: response.mechanic,
        CREATOR: user_to_json(response.creator.user)
        if response.creator is not None
        else None,
        MILESTONE: {ID: response.milestone.id, NAME: response.milestone.name}
        if response.milestone is not None
        else None,
        COURSE: {ID: response.course.id, NAME: response.course.name}
        if response.course is not None
        else None,
    }

    return data