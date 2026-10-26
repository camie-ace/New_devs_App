// Playwright CLI expects a function expression without a trailing semicolon.
// prettier-ignore
async (page) => {
  const origin = new URL(page.url()).origin;
  const pause = (ms) => page.waitForTimeout(ms);
  const chapter = (title, description) =>
    page.screencast.showChapter(title, { description, duration: 2500 });
  const check = async (text) => {
    await page.getByTestId("revenue-total").filter({ hasText: text }).waitFor();
  };
  const login = async (email, password) => {
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/dashboard");
  };
  await page.screencast.showActions({
    cursor: "pointer",
    duration: 500,
    style: { title: "display:none", highlight: "outline: 2px solid #2563eb" },
  });
  if (
    await page.getByRole("button", { name: "Logout", exact: true }).isVisible()
  ) {
    await page.getByRole("button", { name: "Logout", exact: true }).click();
    await page.waitForURL("**/login");
    await page.waitForLoadState("networkidle");
  }
  if (new URL(page.url()).pathname !== "/login")
    await page.goto(origin + "/login");
  await chapter(
    "PropertyFlow debugging verification",
    "Original application and seed data. Both supplied client accounts.",
  );
  await login("sunset@propertyflow.com", "client_a_2024");
  await check("USD 2,250.00");
  await chapter(
    "Sunset: March 2024",
    "Four bookings. The Paris month-boundary reservation belongs to March.",
  );
  await pause(2000);
  await page.getByLabel("Reporting month").fill("2024-02");
  await check("USD 0.00");
  await chapter(
    "February correctly excludes the booking",
    "2024-02-29 23:30 UTC is March 1 at 00:30 in Paris.",
  );
  await pause(1500);
  await page.getByLabel("Reporting month").fill("2024-03");
  await check("USD 2,250.00");
  await page.getByLabel("Show full year").check();
  await check("USD 2,250.00");
  await chapter(
    "Annual reports use the same calculation",
    "Aware local calendar boundaries; exact NUMERIC sum; one Decimal rounding step.",
  );
  await pause(1500);
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  await page.waitForURL("**/login");
  await page.waitForLoadState("networkidle");
  await login("ocean@propertyflow.com", "client_b_2024");
  await page.getByLabel("Select Property").selectOption("prop-001");
  await check("USD 0.00");
  const names = await page
    .getByLabel("Select Property")
    .locator("option")
    .allTextContents();
  if (
    names.some(
      (name) => name.includes("Beach House") || name.includes("Country Villa"),
    )
  )
    throw new Error("Foreign property label leaked");
  await chapter(
    "Ocean: same property ID, separate data",
    "Mountain Lodge Beta is prop-001 too. Zero seeded bookings; no Sunset revenue or property names.",
  );
  await pause(2500);
  await page.reload();
  await page.getByLabel("Select Property").selectOption("prop-001");
  await check("USD 0.00");
  await chapter(
    "Isolation survives refresh and warm caches",
    "Cache keys include tenant, property and reporting period. The API validates property ownership.",
  );
  await pause(2000);
  await page.getByLabel("Select Property").selectOption("prop-005");
  await check("USD 3,256.00");
  await pause(1500);
  await chapter(
    "Verification complete",
    "Both accounts, monthly and annual reporting, tenant-specific properties, exact totals and refresh isolation.",
  );
  return {
    result: "pass",
    sunsetMarch: "2250.00",
    oceanSharedProperty: "0.00",
    oceanLoft: "3256.00",
  };
}
