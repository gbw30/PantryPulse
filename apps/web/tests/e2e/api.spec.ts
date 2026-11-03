import { expect, test } from "@playwright/test";

const apiURL = `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? "8011"}`;

test("process liveness reports its bounded scope against the real FastAPI process", async ({ request }) => {
  const response = await request.get(`${apiURL}/api/v1/health`);
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: "ok", scope: "process" });
  const schema = await request.get(`${apiURL}/openapi.json`);
  expect(schema.status()).toBe(200);
  const document = await schema.json();
  expect(document.paths["/api/v1/health"].get.responses["200"]).toBeDefined();
});

test("US-07 @story unimplemented allocation does not fabricate a successful plan", async ({ request }) => {
  const response = await request.post(`${apiURL}/api/v1/scenarios/example/plans`, { data: {} });
  expect(response.status()).toBe(404);
  expect(await response.json()).toEqual({ detail: "Not Found" });
});
