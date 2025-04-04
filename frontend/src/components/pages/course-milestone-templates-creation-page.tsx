import { Paper, Space, Title } from "@mantine/core";
import { useLocation, useNavigate } from "react-router-dom";
import useGetCourseId from "../../custom-hooks/use-get-course-id";
import useGetMilestoneAlias from "../../custom-hooks/use-get-milestone-alias";
import { useCreateTemplateMutation } from "../../redux/services/templates-api";
import { TemplateData, TemplatePostData } from "../../types/templates";
import toastUtils from "../../utils/toast-utils";
import MilestoneTemplateFormBuilder, {
  MilestoneTemplateFormBuilderData,
} from "../milestone-template-form-builder";

function CourseMilestoneTemplatesCreationPage() {
  const { capitalizedMilestoneAlias } = useGetMilestoneAlias();
  const courseId = useGetCourseId();
  const [createTemplate, { isCreating }] = useCreateTemplateMutation({
    selectFromResult: ({ isLoading: isCreating }) => ({ isCreating }),
  });
  const navigate = useNavigate();

  const onCreateTemplate = async (
    formData: MilestoneTemplateFormBuilderData,
  ) => {
    if (isCreating || courseId === undefined) {
      return;
    }

    const newTemplate = await createTemplate({
      ...(formData as TemplatePostData),
      courseId,
    }).unwrap();

    toastUtils.success({
      message: "The new template has been created successfully.",
    });

    navigate(`../${newTemplate.id}`);
  };

  // Retrieve the template data from the state if it exists
  const location = useLocation();
  const state = location.state as { milestoneTemplateData?: TemplateData };
  const templateData = state?.milestoneTemplateData;

  return (
    <Paper withBorder shadow="sm" p="md" radius="md">
      <Title order={3}>{capitalizedMilestoneAlias} Template Creation</Title>

      <Space h="md" />

      <MilestoneTemplateFormBuilder
        onSubmit={onCreateTemplate}
        submitButtonProps={{ children: "Create" }}
        {...(templateData && { defaultValues: templateData })}
      />
    </Paper>
  );
}

export default CourseMilestoneTemplatesCreationPage;
