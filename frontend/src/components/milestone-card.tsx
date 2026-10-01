/**
 * @changelog
 * | Version | Description                                            | Reference                                     |
 * | v1.0.0 | Initial implementation (indexed baseline)              |                                               |
 * | v1.1.0 | Teacher-only Excel export action: icon button in the card header, loading + error Alert | REQ: 20260929-Excel导出功能升级 TECH: 04_design_tech-design.md §3.5.3 |
 * /@changelog
 *
 * @author chuckyang123
 */
import {
  ActionIcon,
  Alert,
  Badge,
  createStyles,
  Group,
  Paper,
  Stack,
  Tooltip,
} from "@mantine/core";
import { HiEyeOff } from "react-icons/hi";
import { TbFileExport } from "react-icons/tb";
import { MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import useCanExportMilestoneExcel from "../custom-hooks/use-can-export-milestone-excel";
import useGetCourseId from "../custom-hooks/use-get-course-id";
import useGetMilestoneAlias from "../custom-hooks/use-get-milestone-alias";
import useGetMilestonePermissions from "../custom-hooks/use-get-milestone-permissions";
import { useExportMilestoneExcelMutation } from "../redux/services/feedback-api";
import { MilestoneData } from "../types/milestones";
import MilestoneActionsMenu from "./milestone-actions-menu";
import MilestoneActivePeriodDisplay from "./milestone-active-period-display";
import ConditionalRenderer from "./conditional-renderer";
import TextViewer from "./text-viewer";
import { checkIsMilestoneOpen } from "../utils/misc-utils";

const useStyles = createStyles((_, { canAccess }: { canAccess?: boolean }) => ({
  card: {
    cursor: canAccess ? "pointer" : "not-allowed",
  },
  contentContainer: {
    height: "100%",
  },
}));

type Props = MilestoneData;

function MilestoneCard(props: Props) {
  const { milestoneAlias } = useGetMilestoneAlias();
  const navigate = useNavigate();
  const { canAccess, canModify, canDelete } = useGetMilestonePermissions(props);
  const { classes } = useStyles({ canAccess });

  const { name, startDateTime, endDateTime, isPublished, id } = props;
  const isOpen = checkIsMilestoneOpen(props);

  const courseId = useGetCourseId();
  const canExport = useCanExportMilestoneExcel();
  const [exportMilestoneExcel, { isLoading: isExporting, error: exportError }] =
    useExportMilestoneExcelMutation();

  let exportErrorMessage = "Export failed. Please try again.";
  if (
    exportError &&
    "data" in exportError &&
    typeof exportError.data === "object" &&
    exportError.data !== null &&
    "detail" in exportError.data
  ) {
    exportErrorMessage = String(
      (exportError.data as { detail: unknown }).detail,
    );
  }

  const downloadExcel = async (event: MouseEvent<HTMLButtonElement>) => {
    // The card itself navigates on click, so the export action stops bubbling.
    event.stopPropagation();
    if (courseId === undefined) {
      return;
    }
    try {
      await exportMilestoneExcel({ courseId, milestoneId: id }).unwrap();
    } catch {
      // Rendered by the alert below; never retry an export automatically.
    }
  };

  return (
    <Paper
      onClick={canAccess ? () => navigate(`${id}`) : undefined}
      withBorder
      shadow="sm"
      p="md"
      radius="md"
      className={classes.card}
    >
      <Stack
        className={classes.contentContainer}
        spacing="xs"
        justify="space-between"
      >
        <Stack spacing="xs">
          <Group noWrap spacing={4} position="apart" align="flex-start">
            <TextViewer overflowWrap weight={600} size="lg">
              {name}
            </TextViewer>
            <Group noWrap spacing={4}>
              <ConditionalRenderer allow={canExport}>
                <Tooltip
                  label={`Export ${milestoneAlias} answers as Excel`}
                  withinPortal
                >
                  <ActionIcon
                    variant="subtle"
                    color="blue"
                    loading={isExporting}
                    disabled={isExporting}
                    onClick={downloadExcel}
                    aria-label={`Export ${milestoneAlias} answers as Excel`}
                  >
                    <TbFileExport size={18} />
                  </ActionIcon>
                </Tooltip>
              </ConditionalRenderer>
              <ConditionalRenderer allow={canModify || canDelete}>
                <MilestoneActionsMenu {...props} />
              </ConditionalRenderer>
            </Group>
          </Group>
          <MilestoneActivePeriodDisplay
            startDateTime={startDateTime}
            endDateTime={endDateTime}
            size="sm"
            weight={500}
          />
          <div>
            <Badge variant="outline" color={isOpen ? "green" : "red"}>
              {isOpen ? "Open" : "Closed"}
            </Badge>
          </div>
        </Stack>
        {/* <FlexSpacer /> */}

        {!isPublished && (
          <Alert
            p="xs"
            color="orange"
            icon={<HiEyeOff />}
            title="Not published"
          >
            Students cannot view this {milestoneAlias}.
          </Alert>
        )}
        {exportError && (
          <Alert p="xs" color="red" title="Excel export failed">
            {exportErrorMessage}
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}

export default MilestoneCard;
