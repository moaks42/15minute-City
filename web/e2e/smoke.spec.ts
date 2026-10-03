import { expect, test } from '@playwright/test'

// city → persona → criteria → results → places → detail → twins, for both cities.
for (const city of ['krakow', 'praha'] as const) {
  test(`smoke: ${city}`, async ({ page, isMobile }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))

    await page.goto('/')
    await page.getByTestId(`city-${city}`).click()
    await expect(page).toHaveURL(new RegExp(`/${city}`))
    // The language follows the browser (Playwright: en-US), never the city.
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    // Two steps: picking a persona moves on to the criteria.
    await expect(page.getByText('Step 1 of 2')).toBeVisible()
    await page.getByTestId('persona-student').click()
    await expect(page.getByTestId('criterion-transit')).toBeVisible()
    await expect(page.getByText('Step 2 of 2')).toBeVisible()
    await expect(page.getByTestId('wizard-next')).toHaveCount(0)
    await page.getByTestId('show-results').click()

    const cards = page.getByTestId('place-card')
    await expect(cards.first()).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('legend')).toBeVisible()

    // Places and limits live in the results now.
    if (isMobile) await page.getByTestId('open-filters').click()
    const places = page.getByTestId('places-section').last()
    await places.getByTestId('places-toggle').click()
    await expect(places.getByTestId('geo-search')).toBeVisible()
    if (isMobile) {
      await page.keyboard.press('Escape')
    } else {
      // Desktop panels collapse to a rail and open again.
      await page.getByTestId('collapse-left').click()
      await expect(page.getByTestId('places-section')).toHaveCount(0)
      await page.getByTestId('rail-left').click()
      await expect(page.getByTestId('places-section')).toBeVisible()
    }

    // Tap near the top of the card: on mobile the collapsed sheet shows only its upper part.
    await cards.first().getByRole('button').first().click({ position: { x: 40, y: 24 } })
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
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByTestId('detail').last()).toBeVisible()

    expect(errors, isMobile ? 'mobile' : 'desktop').toEqual([])
  })
}

test('a chosen language survives reload and city choice', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('radio', { name: 'cs' }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'cs')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'cs')
  await page.getByTestId('city-krakow').click()
  await expect(page).toHaveURL(/\/krakow/)
  await expect(page.locator('html')).toHaveAttribute('lang', 'cs')
})
