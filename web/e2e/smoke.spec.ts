import { expect, test } from '@playwright/test'

// city → persona → results → detail → twins, for both cities.
for (const city of ['krakow', 'praha'] as const) {
  test(`smoke: ${city}`, async ({ page, isMobile }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))

    await page.goto('/')
    await page.getByTestId(`city-${city}`).click()
    await expect(page).toHaveURL(new RegExp(`/${city}`))
    // Language follows the city.
    await expect(page.locator('html')).toHaveAttribute('lang', city === 'krakow' ? 'pl' : 'cs')

    await page.getByTestId('persona-student').click()
    await expect(page.getByTestId('criterion-transit')).toBeVisible()
    await page.getByTestId('show-results').click()

    const cards = page.getByTestId('place-card')
    await expect(cards.first()).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('legend')).toBeVisible()

    await cards.first().getByRole('button').first().click()
    const detail = page.getByTestId('detail').last()
    await expect(detail).toBeVisible()
    await expect(detail.getByTestId('archetype')).toBeVisible()

    const twin = detail.getByTestId('twin').first()
    await twin.scrollIntoViewIfNeeded()
    await expect(twin).toBeVisible({ timeout: 15_000 })
    await twin.click()
    const other = city === 'krakow' ? 'praha' : 'krakow'
    await expect(page).toHaveURL(new RegExp(`/${other}\\?`))
    // Persona survives the city switch; language stays.
    await expect(page).toHaveURL(/p=student/)
    await expect(page.locator('html')).toHaveAttribute('lang', city === 'krakow' ? 'pl' : 'cs')
    await expect(page.getByTestId('detail').last()).toBeVisible()

    expect(errors, isMobile ? 'mobile' : 'desktop').toEqual([])
  })
}
