import { Button, Text, Stack, Paper, Blockquote, Title } from "@mantine/core";
import { useFormContext } from "react-hook-form";
import { IoGameControllerOutline } from "react-icons/io5";
import { TbMessageChatbot } from "react-icons/tb";
import { useContext } from "react";
import Markdown, { Components } from "react-markdown";
import { useState, useEffect } from "react";
import { useResolveError } from "../utils/error-utils";
import {
  useCreateInitialResponseIfNotExistsMutation,
} from "../redux/services/feedback-api";
import { FeedbackContext } from "../contexts/feedback-data-collection-provider";

type Props = {
  name: string;
  question: string;
  collectData: boolean | undefined;
};

const markdownComponents: Partial<Components> = {
  h1: ({ node, children }) => <Title order={1}>{children}</Title>,
  h2: ({ node, children }) => <Title order={2}>{children}</Title>,
  h3: ({ node, children }) => (
    <Title order={4} mb="md">
      {children}
    </Title>
  ),
  h4: ({ node, children }) => (
    <Title order={5} mb="xs">
      {children}
    </Title>
  ),
  p: ({ node, children }) => <Text size="sm">{children}</Text>,
  li: ({ node, children }) => (
    <Text size="sm" component="li" mb="xs">
      {children}
    </Text>
  ),
  strong: ({ node, children }) => <Text weight={700}>{children}</Text>,
};

function FormFieldPlaytestFeedbackRenderer({ name, question, collectData }: Props) {
  // const { getValues } = useFormContext<{ [name: string]: string }>();
  const{ getValues} = useFormContext();
  const { resolveError } = useResolveError({ name: "form-field-playtest-feedback-renderer" });
  const feedbackContext = useContext(FeedbackContext);

  const [isFetching, setisFetching] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [promptText, setPromptText] = useState<string>("");
  const [inputError, setInputError] = useState<string | null>(null);


  useEffect(() => {
    const fetchPrompt = async () => {
      try {
        const res = await fetch("/prompt_for_playtest_feedback.txt");
        const text = await res.text();
        setPromptText(text);
      } catch (error) {
        console.error("Failed to load prompt file:", error);
      }
    };
    fetchPrompt();
  }, []);


  const [tryStoreInitialResponse, { isLoading }] =
    useCreateInitialResponseIfNotExistsMutation({
      selectFromResult: ({ isLoading }) => ({ isLoading }),
    });

  const onGenerateFeedback = async () => {
    setInputError(null);
    const content = getValues(name) as string;
    const genre = getValues("Genre") as string;
    const mechanic = getValues("Mechanic") as string;
    console.log("genre:", genre, "mechanic:", mechanic);
    if (!genre || !mechanic) {
      setInputError("Please select both a genre and a mechanic before generating feedback.");
      return;
    }
    if (!content || isFetching || isLoading) return;


    const fullQuery = `
      ${promptText}
      Genre: ${genre}
      Main Mechanic: ${mechanic}
      Question: ${question}
      Answer: ${content}
    `;

    try {
      setisFetching(true);
      const res = await fetch("/api/playtest/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "your-secure-api-key-here",
        },
        body: JSON.stringify({ query: fullQuery, mode: "hybrid" }),
      });

      const raw = await res.json() as { response?: string };
      setFeedback(raw.response ?? "No feedback returned.");
    } catch (err) {
      resolveError(err);
    } finally {
      setisFetching(false);
    }

    // If form in test mode, responses not considered
    if (feedbackContext.testMode || !feedbackContext.submissionId) {
      return;
    }

    const feedbackPostData = {
      submission_id: feedbackContext.submissionId,
      question: question,
      genre: genre,
      mechanic: mechanic,
      initial_response: content,
    };

    try {

      await tryStoreInitialResponse(feedbackPostData).unwrap();
      console.log("Saved initial response:", feedbackPostData);

    } catch (error) {

      resolveError(error);
    }
  };

  return (
    <Stack>
      <div>
        <Button
          leftIcon={<IoGameControllerOutline />}
          compact
          loading={isFetching}
          onClick={onGenerateFeedback}
        >
          {isFetching ? "Generating" : "Generate"} feedback
        </Button>
      </div>
      {inputError && (
        <Text color="red" mt="sm" size="sm">
          {inputError}
        </Text>
      )}
      {feedback && (
        <Blockquote color="blue" mt="xl" icon={<TbMessageChatbot size={30} />}>
          <Paper withBorder shadow="xl" p="xl">
            <Text size="sm">
              Here is some feedback on what you have written:
              <br />
              <br />
            </Text>
            <Markdown components={markdownComponents}>
              {feedback}
            </Markdown>
          </Paper>
        </Blockquote>
      )}
    </Stack>
  );
}


export default FormFieldPlaytestFeedbackRenderer;


