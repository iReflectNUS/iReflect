import { useEffect } from "react";
import { Box, Container, createStyles, Group } from "@mantine/core";
import Head from "next/head";
import ColorModeToggler from "../color-mode-toggler";
import LoginSection from "../login-section";
import { APP_NAME } from "../../constants";
import resetAppState from "../../redux/thunks/reset-app-state";
import { colorModeValue } from "../../utils/theme-utils";
import { useAppDispatch } from "../../redux/hooks";

interface LoginPageProps {
  isPasswordReset?: boolean;
}

const useStyles = createStyles((theme) => ({
  main: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    backgroundColor: colorModeValue(theme.colorScheme, {
      lightModeValue: theme.colors.gray[0],
      darkModeValue: theme.colors.dark[8],
    }),
    backgroundImage: colorModeValue(theme.colorScheme, {
      lightModeValue: `url(https://i.imgur.com/S19lB66.png)`,
      darkModeValue: `url(https://i.imgur.com/xk8SGwG.png)`,
    }),
    backgroundPosition: "center",
    backgroundSize: "cover",
    backgroundRepeat: "no-repeat",
  },
  container: {
    width: "100%",
  },
}));

function LoginPage({ isPasswordReset }: LoginPageProps) {
  const dispatch = useAppDispatch();
  const { classes } = useStyles();

  useEffect(() => {
    dispatch(resetAppState());
  }, [dispatch]);

  return (
    <>
      <Head>
        <title>Login | {APP_NAME}</title>
      </Head>

      <Box<"main"> component="main" className={classes.main} pt="xs" pb="md">
        <Group position="right" px="md">
          <ColorModeToggler />
        </Group>

        <Container className={classes.container} size={500} p={32}>
          <LoginSection isPasswordReset={isPasswordReset} />
        </Container>
      </Box>
    </>
  );
}

export default LoginPage;
