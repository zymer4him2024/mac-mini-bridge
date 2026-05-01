import { expect, test } from "@playwright/test";

const locales = [
  { locale: "en", expectedHeadline: "Read once. Ask anything." },
  { locale: "ko", expectedHeadline: "한 번 읽고, 무엇이든 물어보세요." },
  { locale: "pt-BR", expectedHeadline: "Leia uma vez. Pergunte qualquer coisa." },
];

for (const { locale, expectedHeadline } of locales) {
  test.describe(`sign-in page — ${locale}`, () => {
    test(`renders the localized headline at /${locale}/sign-in`, async ({ page }) => {
      await page.goto(`/${locale}/sign-in`);

      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(expectedHeadline);
    });

    test(`Continue-with-Google button is keyboard-focusable at /${locale}/sign-in`, async ({
      page,
    }) => {
      await page.goto(`/${locale}/sign-in`);

      const button = page.getByRole("button");
      await expect(button).toBeVisible();

      await page.keyboard.press("Tab");
      await expect(button).toBeFocused();
    });
  });
}

test("the root path redirects to the default locale", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.url()).toMatch(/\/en(\/|$)/);
});
