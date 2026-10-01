/**
 * @changelog
 * | Version | Description                                            | Reference                                     |
 * | v1.0.0 | Initial implementation: score visibility follows the course role, not account_type | BUG: teacher-scores-hidden |
 * /@changelog
 *
 * @author chuckyang123
 */
import { useGetSingleCourseQuery } from "../redux/services/courses-api";
import { Role } from "../types/courses";
import { AccountType } from "../types/users";
import useGetCourseId from "./use-get-course-id";
import useGetCurrentUserAccountType from "./use-get-current-user-account-type";

/**
 * True only for students of a course that disabled showAiScore.
 *
 * The COURSE role decides who is a teacher: invited instructors and co-owners
 * usually keep accountType STANDARD, so the old accountType check treated them
 * as students and hid every score from them (BUG: teacher-scores-hidden — the
 * same class of bug the backend fixed in feedback/views.py v1.6.0).
 */
export default function useShouldHideAiScores(): boolean {
  const courseId = useGetCourseId();
  const accountType = useGetCurrentUserAccountType();
  const { data: course } = useGetSingleCourseQuery(courseId ?? "", {
    skip: !courseId,
  });

  const canSeeScores =
    accountType === AccountType.Admin ||
    accountType === AccountType.Educator ||
    course?.role === Role.CoOwner ||
    course?.role === Role.Instructor;

  return !canSeeScores && course?.showAiScore === false;
}
