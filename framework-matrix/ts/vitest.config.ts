import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globalSetup: ["./src/globalSetup.ts"],
    testTimeout: 240_000,
    hookTimeout: 240_000,
    include: ["test/**/*.test.ts"],
  },
});
