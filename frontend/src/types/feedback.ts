import {
  ANNOTATED_CONTENT,
  CONTENT,
  CREATED,
  FEEDBACK,
  INITIAL_RESPONSE,
  QUESTION,
  SUBMISSION_ID,
  PLAYTEST_MODE,
  PLAYTEST_RESPONSE,
  PLAYTEST_QUERY,
} from "../constants";
import { BaseData } from "./base";

export type FeedbackData = {
  [ANNOTATED_CONTENT]: string;
  [FEEDBACK]: string;
};

export type FeedbackPostData = {
  [CONTENT]: string;
};

export type FeedbackInitialResponseData = {
  [CREATED]: boolean;
  [INITIAL_RESPONSE]: string;
};

export type FeedbackInitialResponsePostData = Partial<BaseData> & {
  [SUBMISSION_ID]: string | number;
  [QUESTION]: string;
  [INITIAL_RESPONSE]: string;
};

export type PlaytestPostData = {
  [PLAYTEST_QUERY]: string;
  [PLAYTEST_MODE]: string;
};

export type PlaytestResponseData = {
  [PLAYTEST_RESPONSE]: string;
};
