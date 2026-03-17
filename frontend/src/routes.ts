import { createBrowserRouter } from "react-router";
import { HomePage } from "./pages/HomePage";
import { ResultsPage } from "./pages/ResultsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: HomePage,
  },
  {
    path: "/results",
    Component: ResultsPage,
  },
]);