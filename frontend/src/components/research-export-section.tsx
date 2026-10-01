import { useCallback, useRef, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { TbDownload } from "react-icons/tb";
import { useExportResearchDataMutation } from "../redux/services/feedback-api";

type Props = { courseId: string | number };

export default function ResearchExportSection({ courseId }: Props) {
  const [scope, setScope] = useState<"course" | "all">("course");
  const [includeIdentity, setIncludeIdentity] = useState(false);
  const [exportData, { isLoading, isSuccess, error }] =
    useExportResearchDataMutation();
  const inFlight = useRef(false);
  let errorMessage =
    "Export failed. Please try again or select a smaller scope.";
  if (
    error &&
    "data" in error &&
    typeof error.data === "object" &&
    error.data !== null &&
    "detail" in error.data
  ) {
    errorMessage = String((error.data as { detail: unknown }).detail);
  }

  const download = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      await exportData({
        scope,
        ...(scope === "course" ? { courseId } : {}),
        includeIdentity,
      }).unwrap();
    } catch {
      // The mutation error is displayed below; never automatically re-export.
    } finally {
      inFlight.current = false;
    }
  }, [exportData, scope, courseId, includeIdentity]);

  return (
    <Stack spacing="sm">
      <Title order={5}>Export research data</Title>
      <Text size="sm" color="dimmed">
        Download all saved answers, versions, AI feedback, scores and comparison
        pairs for analysis outside iReflect. Exporting does not call AI.
      </Text>
      <Select
        label="Export scope"
        value={scope}
        onChange={(value) => setScope(value === "all" ? "all" : "course")}
        data={[
          { value: "course", label: "All research data in this course" },
          { value: "all", label: "All courses I can manage" },
        ]}
        disabled={isLoading}
      />
      <Checkbox
        label="Include a separate student and teacher identity map (names and emails)"
        checked={includeIdentity}
        onChange={(event) => setIncludeIdentity(event.currentTarget.checked)}
        disabled={isLoading}
      />
      <Text size="xs" color="dimmed">
        Raw answers may contain names even without the identity map. The archive
        includes recorded history and current submissions, not unrecorded edits
        or attachment files.
      </Text>
      <Button
        leftIcon={<TbDownload size={16} />}
        loading={isLoading}
        onClick={download}
      >
        {isLoading ? "Preparing research archive…" : "Export all research data"}
      </Button>
      {isSuccess && !isLoading && (
        <Text size="sm" color="green">
          Research archive download started.
        </Text>
      )}
      {error && (
        <Alert color="red" title="Export could not be completed">
          {errorMessage}
        </Alert>
      )}
    </Stack>
  );
}
