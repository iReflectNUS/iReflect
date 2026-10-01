/**
 * @changelog
 * | Version | Description                                            | Reference                                     |
 * | v1.0.0 | Initial implementation: feedback endpoints              |                                               |
 * | v1.1.0 | Added exportMilestoneExcel mutation (per-milestone xlsx)| REQ: 20260929-Excel导出功能升级 TECH: 04_design_tech-design.md §3.5.3 |
 * /@changelog
 *
 * @author chuckyang123
 */
import { saveAs } from "file-saver";
import {
  FeedbackData,
  FeedbackInitialResponseData,
  FeedbackInitialResponsePostData,
  FeedbackPostData,
  FeedbackRecordPostData,
  FeedbackRecordQueryParams,
  FeedbackRecordResponseData,
  FeedbackVersionHistoryData,
} from "../../types/feedback";
import baseApi from "./base-api";

const feedbackApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    exportResearchData: build.mutation<
      { downloaded: boolean },
      {
        scope: "course" | "all";
        courseId?: string | number;
        includeIdentity: boolean;
      }
    >({
      async queryFn(data, _api, _extraOptions, baseQuery) {
        const result = await baseQuery({
          url: "/feedback/research-export/",
          method: "POST",
          body: data,
          responseHandler: async (response) => {
            if (response.ok) return response.blob();
            const message = await response.text();
            try {
              return JSON.parse(message) as unknown;
            } catch {
              return {
                detail: "Export failed. Please try a smaller course scope.",
              };
            }
          },
        });
        if (result.error) return { error: result.error };
        if (!(result.data instanceof Blob)) {
          return {
            error: {
              status: "CUSTOM_ERROR",
              error: "Invalid export response.",
            },
          };
        }
        // Keep the archive out of Redux state; existing authenticated baseQuery
        // handles token refresh, and the download stays on the user's device.
        saveAs(
          result.data,
          `ireflect-research-${new Date()
            .toISOString()
            .replace(/[:.]/g, "-")}.zip`,
        );
        return { data: { downloaded: true } };
      },
    }),
    exportMilestoneExcel: build.mutation<
      { downloaded: boolean },
      { courseId: string | number; milestoneId: string | number }
    >({
      async queryFn(data, _api, _extraOptions, baseQuery) {
        const result = await baseQuery({
          url: "/feedback/milestone-export/",
          method: "POST",
          body: data,
          responseHandler: async (response) => {
            if (response.ok) return response.blob();
            const message = await response.text();
            try {
              return JSON.parse(message) as unknown;
            } catch {
              return {
                detail: "Export failed. Please try again.",
              };
            }
          },
        });
        if (result.error) return { error: result.error };
        if (!(result.data instanceof Blob)) {
          return {
            error: {
              status: "CUSTOM_ERROR",
              error: "Invalid export response.",
            },
          };
        }
        saveAs(
          result.data,
          `ireflect-${data.courseId}-${data.milestoneId}-${new Date()
            .toISOString()
            .replace(/[:.]/g, "-")}.xlsx`,
        );
        return { data: { downloaded: true } };
      },
    }),
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
    getFeedbackAnswerVersions: build.query<
      FeedbackVersionHistoryData[],
      FeedbackRecordQueryParams
    >({
      query: (params) => ({
        url: "/feedback/records/",
        method: "GET",
        params,
      }),
    }),
  }),
});

export const {
  useExportResearchDataMutation,
  useExportMilestoneExcelMutation,
  useLazyGetFeedbackQuery,
  useCreateInitialResponseIfNotExistsMutation,
  useCreateFeedbackRecordMutation,
  useGetFeedbackAnswerVersionsQuery,
} = feedbackApi;
