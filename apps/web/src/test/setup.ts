import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// findBy*/waitFor wait up to 5 s: the flows stream every tutor turn word by word, and CI can be slow.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => cleanup());
