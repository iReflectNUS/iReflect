import { Route, Routes, Navigate, Outlet } from "react-router-dom";
import { useAppSelector } from "../redux/hooks";
import { selectIsLoggedIn } from "../redux/slices/current-user-slice";
import {
  DASHBOARD_PATH,
  LOGIN_PATH,
  MY_ACCOUNT_PATH,
  MY_COURSES_PATH,
} from "./paths";
import AppLayout from "../components/app-layout";
import LoginPage from "../components/pages/login-page";
import DashboardPage from "../components/pages/dashboard-page";
import MyCoursesPage from "../components/pages/my-courses-page";
import MyAccountPage from "../components/pages/my-account-page";

function RouteHandler() {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);

  return (
    <Routes>
      {isLoggedIn ? (
        <>
          <Route path={LOGIN_PATH} element={<Navigate to={DASHBOARD_PATH} />} />

          <Route
            element={
              <AppLayout>
                <Outlet />
              </AppLayout>
            }
          >
            <Route path={DASHBOARD_PATH} element={<DashboardPage />} />
            <Route path={MY_COURSES_PATH} element={<MyCoursesPage />} />
            <Route path={MY_ACCOUNT_PATH} element={<MyAccountPage />} />
          </Route>

          <Route path="*" element={<Navigate to={DASHBOARD_PATH} />} />
        </>
      ) : (
        <Route path="*" element={<LoginPage />} />
      )}
    </Routes>
  );
}

export default RouteHandler;