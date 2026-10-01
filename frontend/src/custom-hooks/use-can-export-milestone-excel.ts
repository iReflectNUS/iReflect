/**
 * @changelog
 * | Version | Description                                            | Reference                                     |
 * | v1.0.0 | Initial implementation: teacher-only milestone Excel export permission | REQ: 20260929-Excel导出功能升级 TECH: 04_design_tech-design.md §3.5.3 |
 * /@changelog
 *
 * @author chuckyang123
 */
import { Role } from "../types/courses";
import { AccountType } from "../types/users";
import useGetCurrentUserAccountType from "./use-get-current-user-account-type";
import useGetCurrentUserRole from "./use-get-current-user-role";

/** Mirrors the backend allowed_courses rule: admins, plus course instructors
 * and co-owners. Students never see the export action. */
export default function useCanExportMilestoneExcel() {
  const role = useGetCurrentUserRole();
  const accountType = useGetCurrentUserAccountType();

  if (accountType === AccountType.Admin) {
    return true;
  }

  return role !== undefined && [Role.CoOwner, Role.Instructor].includes(role);
}
