import React from "react";
import { skipToken } from "@reduxjs/toolkit/query/react";
import { Group, Paper, Text } from "@mantine/core";
import PlaceholderWrapper from "./placeholder-wrapper";
import { useResolveError } from "../utils/error-utils";
import { useGetSubmissionViewableGroupsQuery } from "../redux/services/submissions-api";
import CourseSubmissionPublishPopover from "./course-submission-publish-popover";

type CourseSubmissionPublishSectionProps = {
  courseId?: number | string;
  submissionId?: number | string;
  disabled?: boolean;
};

const CourseSubmissionPublishSection = ({
  courseId,
  submissionId,
  disabled,
}: CourseSubmissionPublishSectionProps) => {
  const { viewableGroups, isLoadingViewableGroups, error } =
    useGetSubmissionViewableGroupsQuery(
      courseId === undefined || submissionId === undefined
        ? skipToken
        : { courseId, submissionId },
      {
        selectFromResult: ({
          data: viewableGroups,
          isLoading: isLoadingViewableGroups,
          error,
        }) => ({
          viewableGroups,
          isLoadingViewableGroups,
          error,
        }),
      },
    );

  useResolveError({ error, name: "course-submission-publish-section" });

  if (isLoadingViewableGroups) {
    return (
      <PlaceholderWrapper
        py={150}
        isLoading={isLoadingViewableGroups}
        loadingMessage="Loading publishing status..."
      />
    );
  }

  return (
    <Group spacing={12}>
      <Text size="sm">Currently published to:</Text>
      <Paper withBorder p={6}>
        <Text size="sm">
          {viewableGroups &&
            viewableGroups.map((group) => group.name).join(", ")}
        </Text>
      </Paper>
      <CourseSubmissionPublishPopover
        courseId={courseId}
        submissionId={submissionId}
        viewableGroups={viewableGroups ?? []}
        disabled={disabled}
      />
      {disabled && (
        <Text size="sm" color="orange">
          Save your changes before changing publishing status.
        </Text>
      )}
    </Group>
  );
};

export default CourseSubmissionPublishSection;
