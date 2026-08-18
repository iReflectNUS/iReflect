import {
  FeedbackData,
  FeedbackInitialResponseData,
  FeedbackInitialResponsePostData,
  FeedbackPostData,
  FeedbackRecordPostData,
  FeedbackRecordResponseData,
} from "../../types/feedback";
import baseApi from "./base-api";

const feedbackApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getFeedback: build.query<FeedbackData, FeedbackPostData>({
      query: (data) => ({
        url: "/feedback/",
        method: "POST",
        body: data,
      }),
    }),
    createInitialResponseIfNotExists: build.mutation<
      FeedbackInitialResponseData,
      FeedbackInitialResponsePostData
    >({
      query: ({ ...feedbackPostData }) => ({
        url: "/feedback/initial-response/",
        method: "POST",
        body: feedbackPostData,
      }),
    }),
    createFeedbackRecord: build.mutation<
      FeedbackRecordResponseData,
      FeedbackRecordPostData
    >({
      query: ({ ...feedbackRecordPostData }) => ({
        url: "/feedback/records/",
        method: "POST",
        body: feedbackRecordPostData,
      }),
    }),
  }),
});

export const {
  useLazyGetFeedbackQuery,
  useCreateInitialResponseIfNotExistsMutation,
  useCreateFeedbackRecordMutation,
} = feedbackApi;
