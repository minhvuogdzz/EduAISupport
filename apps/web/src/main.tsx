import "@fontsource-variable/lexend";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { createApi } from "./api";
import { App } from "./App";
import { AppProviders } from "./AppProviders";
import { createQueryClient } from "./queryClient";

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <AppProviders api={createApi()} queryClient={createQueryClient()}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AppProviders>
  </StrictMode>,
);
