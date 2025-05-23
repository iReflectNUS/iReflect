import { ElementRef, useMemo, useRef } from "react";
import { Button, Group, Paper, Select, Stack, Text } from "@mantine/core";
import { useDidUpdate } from "@mantine/hooks";
import { useModals } from "@mantine/modals";
import { skipToken } from "@reduxjs/toolkit/query/react";
import { RiFileCopyLine, RiFileEditLine } from "react-icons/ri";
import { FaTrashAlt } from "react-icons/fa";
import { generatePath, Link, useNavigate } from "react-router-dom";
import useGetCourseId from "../../custom-hooks/use-get-course-id";
import useGetTemplateId from "../../custom-hooks/use-get-template-id";
import {
  useDeleteTemplateMutation,
  useGetTemplatesQueryState,
} from "../../redux/services/templates-api";
import { COURSE_MILESTONE_TEMPLATES_PATH } from "../../routes/paths";
import { useResolveError } from "../../utils/error-utils";
import toastUtils from "../../utils/toast-utils";
import SubmissionForm from "../submission-form";
import PlaceholderWrapper from "../placeholder-wrapper";
import useGetTemplatePermissions from "../../custom-hooks/use-get-template-permissions";
import ConditionalRenderer from "../conditional-renderer";
import useGetFormContainerStyle from "../../custom-hooks/use-get-form-container-style";
import { transformTemplateToSubmissionView } from "../../utils/transform-utils";
import MilestoneTemplateCopyToSelection from "../milestone-template-copy-to-selection";

function CourseMilestoneTemplatesViewPage() {
  const courseId = useGetCourseId();
  const templateId = useGetTemplateId();
  const formContainerClassName = useGetFormContainerStyle();
  const { milestoneTemplates } = useGetTemplatesQueryState(
    courseId ?? skipToken,
    {
      selectFromResult: ({ data: milestoneTemplates }) => ({
        milestoneTemplates,
      }),
    },
  );
  const submissionView = useMemo(
    () =>
      transformTemplateToSubmissionView({
        template: milestoneTemplates?.find(({ id }) => `${id}` === templateId),
      }),
    [templateId, milestoneTemplates],
  );
  const [deleteTemplate, { isDeleting }] = useDeleteTemplateMutation({
    selectFromResult: ({ isLoading: isDeleting }) => ({ isDeleting }),
  });
  const { resolveError } = useResolveError({
    name: "course-milestone-templates-view-page",
  });
  const navigate = useNavigate();
  const modals = useModals();
  const formRef = useRef<ElementRef<typeof SubmissionForm>>(null);
  const { canModify, canDelete } = useGetTemplatePermissions(
    submissionView?.template ?? undefined,
  );

  const onDeleteTemplate = async () => {
    if (isDeleting || courseId === undefined || templateId === undefined) {
      return;
    }

    try {
      await deleteTemplate({ courseId, templateId }).unwrap();

      toastUtils.success({
        message: "The template has been deleted successfully.",
      });

      navigate(
        generatePath(COURSE_MILESTONE_TEMPLATES_PATH, {
          courseId,
        }),
      );
    } catch (error) {
      resolveError(error);
    }
  };

  const openDeleteModal = () =>
    modals.openConfirmModal({
      title: "Delete this template",
      closeButtonLabel: "Cancel template deletion",
      centered: true,
      children: (
        <Text size="sm">
          Are you sure you want to delete this template (
          <strong>{submissionView?.name}</strong>)?
          <br />
          <strong>This action is destructive and irreversible.</strong>
        </Text>
      ),
      labels: { confirm: "Delete template", cancel: "No don't delete" },
      confirmProps: { color: "red" },
      onConfirm: onDeleteTemplate,
    });

  // this is required to tell the form that the submissionView has changed
  // due to useForm ignoring changes to the supplied defaultValues
  useDidUpdate(() => {
    formRef.current?.reset(submissionView);
  }, [submissionView]);

  const openCopyTemplateModal = () => {
    if (!courseId || !templateId) {
      return;
    }

    const id = modals.openModal({
      title: <Text weight="bold">Copy Template to Another Course</Text>,
      children: (
        <MilestoneTemplateCopyToSelection
          navigate={navigate}
          courseId={courseId}
          templateId={templateId}
          onSuccess={() => modals.closeModal(id)}
        />
      ),
      size: "xl",
      centered: true,
    });
  };

  return (
    <PlaceholderWrapper
      py={150}
      defaultMessage="No template found."
      showDefaultMessage={!submissionView}
    >
      {submissionView && (
        <Stack>
          <ConditionalRenderer allow={canModify || canDelete}>
            <Group position="right">
              <ConditionalRenderer allow={canModify}>
                <Button
                  color="teal"
                  onClick={openCopyTemplateModal}
                  leftIcon={<RiFileCopyLine />}
                >
                  Copy Template
                </Button>
              </ConditionalRenderer>
              <ConditionalRenderer allow={canModify}>
                <Button<typeof Link>
                  component={Link}
                  to="edit"
                  leftIcon={<RiFileEditLine />}
                >
                  Edit template
                </Button>
              </ConditionalRenderer>
              <ConditionalRenderer allow={canDelete}>
                <Button
                  color="red"
                  leftIcon={<FaTrashAlt size={12} />}
                  onClick={openDeleteModal}
                  loading={isDeleting}
                >
                  Delete template
                </Button>
              </ConditionalRenderer>
            </Group>
          </ConditionalRenderer>

          <Paper
            withBorder
            shadow="sm"
            p="md"
            radius="md"
            className={formContainerClassName}
          >
            <SubmissionForm
              ref={formRef}
              defaultValues={submissionView}
              testMode
            />
          </Paper>
        </Stack>
      )}
    </PlaceholderWrapper>
  );
}

export default CourseMilestoneTemplatesViewPage;
