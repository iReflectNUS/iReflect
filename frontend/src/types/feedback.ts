import {
  ANNOTATED_CONTENT,
  CONTENT,
  CREATED,
  FEEDBACK,
  FEEDBACK_CONTENT,
  IDEMPOTENCY_KEY,
  INITIAL_RESPONSE,
  QUESTION,
  GENRE,
  MECHANIC,
  RECORD_ID,
  SUBMISSION_ID,
  PLAYTEST_MODE,
  PLAYTEST_RESPONSE,
  PLAYTEST_QUERY,
} from "../constants";
import { BaseData } from "./base";

export type FeedbackData = {
  [ANNOTATED_CONTENT]: string;
  [FEEDBACK]: string;
  [RECORD_ID]?: string | number | null;
};

export type FeedbackPostData = {
  [CONTENT]: string;
  [SUBMISSION_ID]?: string | number;
  [QUESTION]?: string;
};

export type FeedbackInitialResponseData = {
  [CREATED]: boolean;
  [INITIAL_RESPONSE]: string;
};

export type FeedbackInitialResponsePostData = Partial<BaseData> & {
  [SUBMISSION_ID]: string | number;
  [QUESTION]: string;
  [GENRE]?: string;
  [MECHANIC]?: string;
  [INITIAL_RESPONSE]: string;
};

export type FeedbackRecordPostData = {
  [SUBMISSION_ID]: string | number;
  [QUESTION]: string;
  [INITIAL_RESPONSE]: string;
  [FEEDBACK_CONTENT]: string;
  [GENRE]?: string;
  [MECHANIC]?: string;
  [IDEMPOTENCY_KEY]?: string;
};

export type FeedbackRecordResponseData = {
  record: {
    id: string | number;
    [FEEDBACK_CONTENT]: string;
  };
  version: {
    id: string | number;
    version_number: number;
    [INITIAL_RESPONSE]: string;
  };
};

export type PlaytestPostData = {
  [PLAYTEST_QUERY]: string;
  [PLAYTEST_MODE]: string;
};

export type PlaytestResponseData = {
  [PLAYTEST_RESPONSE]: string;
};
