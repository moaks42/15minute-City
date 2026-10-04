import { expect, test } from '@playwright/test'

// welcome search (city + persona) → results → places → detail → twins, for both cities.
for (const city of ['krakow', 'praha'] as const) {
  test(`smoke: ${city}`, async ({ page, isMobile }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))

    await page.goto('/')
    await page.getByTestId('search-city').selectOption(city)
    await page.getByTestId('search-persona').selectOption('student')
    await page.getByTestId('search-submit').click()
    await expect(page).toHaveURL(new RegExp(`/${city}\\?.*p=student`))
    // The language follows the browser (Playwright: en-US), never the city.
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    const cards = page.getByTestId('place-card')
    await expect(cards.first()).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('legend')).toBeVisible()

    // Map lens: every mode keeps its controls inside the switch card.
    await page.getByTestId('mode-commute').click()
    const lens = page.getByTestId('lens-commute')
    await expect(lens).toBeVisible()
    await expect(page.getByTestId('legend')).toHaveCount(0) // nothing to explain until there is a place
    // A place has a name the user gives and an address they pick; nothing is named for them.
    await lens.getByTestId('commute-name').fill('Office')
    await lens.getByTestId('commute-search').fill('ul')
    await page.getByRole('listbox').getByRole('option').first().click()
    await expect(lens.getByTestId('commute-anchor')).toHaveText('Office')
    await expect(page.getByTestId('legend')).toContainText('Travel time to Office')
    await lens.getByTestId('commute-remove').click()
    await expect(lens.getByTestId('commute-anchor')).toHaveCount(0)
    await expect(lens.getByTestId('commute-search')).toBeVisible()
    await page.getByTestId('mode-criterion').click()
    await expect(page.getByTestId('criterion-select')).toBeVisible()
    await page.getByTestId('mode-match').click()
    await expect(page.getByTestId('lens-commute')).toHaveCount(0)

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

test('the wizard still works from a link', async ({ page }) => {
  await page.goto('/krakow?step=persona')
  // Two steps: picking a persona moves on to the criteria.
  await expect(page.getByText('Step 1 of 2')).toBeVisible()
  await page.getByTestId('persona-student').click()
  await expect(page.getByTestId('criterion-transit')).toBeVisible()
  await expect(page.getByText('Step 2 of 2')).toBeVisible()
  await expect(page.getByTestId('wizard-next')).toHaveCount(0)
  await page.getByTestId('show-results').click()
  await expect(page.getByTestId('place-card').first()).toBeVisible({ timeout: 20_000 })
})

test('welcome: needs become limits, collections open their results', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')

  // Every collection lists its live top 3.
  const tops = page.getByRole('list', { name: 'Best matches' })
  await expect(tops).toHaveCount(3)
  for (const list of await tops.all()) await expect(list.getByRole('listitem')).toHaveCount(3)

  // A suggested need turns into a removable chip and reaches the results as a hard limit.
  await page.getByTestId('need-m:park').click()
  await expect(page.getByTestId('need-chip')).toHaveText(/Park within 10 min/)
  await page.getByTestId('add-need').selectOption('noise')
  await expect(page.getByTestId('need-chip')).toHaveCount(2)
  await page.getByTestId('need-chip').first().getByRole('button').click()
  await expect(page.getByTestId('need-chip')).toHaveCount(1)
  await page.getByTestId('search-submit').click()
  await expect(page).toHaveURL(/\/krakow\?.*f=n%3A55/)

  await page.goBack()
  await page.getByTestId('collection-senior').click()
  await expect(page).toHaveURL(/\/praha\?.*p=senior/)
  await expect(page.getByTestId('place-card').first()).toBeVisible({ timeout: 20_000 })
  expect(errors).toEqual([])
})

test('welcome: relocating carries the current address into the results', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('search-home')).toHaveCount(0)
  await page.getByTestId('search-persona').selectOption('expat')
  // City is Kraków, so the address is searched in Prague.
  await expect(page.getByText('I live now in Prague')).toBeVisible()
  await page.getByTestId('search-home').fill('ul')
  await page.getByRole('listbox').getByRole('option').first().click()
  await expect(page.getByTestId('search-home-value')).not.toBeEmpty()
  await page.getByTestId('search-submit').click()
  await expect(page).toHaveURL(/\/krakow\?.*p=expat/)
  await expect(page.getByTestId('expat-twin').first()).toBeAttached({ timeout: 20_000 })
})

test('the results follow the map lens; a district opens as a whole', async ({ page, isMobile }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/praha?v=1&lang=en&p=student')
  const cards = page.getByTestId('place-card')
  await expect(cards.first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId('sorted-by')).toContainText('match')

  // One criterion on the map: the list is ordered by it, and the chip's × goes back to match %.
  await page.getByTestId('mode-criterion').click()
  await page.getByTestId('criterion-select').selectOption('green')
  await expect(page.getByTestId('sorted-by')).toContainText('Green space')
  const badges = cards.getByTestId('lens-badge')
  await expect(badges.first()).toHaveAttribute('title', /Green space/)
  // The previous list stays on screen until the re-ranked one arrives.
  await expect
    .poll(async () => {
      const v = await badges.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-value'))))
      return v.length > 1 && v.every((x, i) => i === 0 || v[i - 1] >= x)
    })
    .toBe(true)
  await page.getByTestId('sort-reset').click()
  await expect(page.getByTestId('mode-match')).toHaveAttribute('aria-checked', 'true')

  // Districts: the card opens the whole district (outline + its own detail), not one hexagon.
  await page.getByTestId('tab-districts').click()
  await cards.first().getByRole('button').first().click({ position: { x: 40, y: 24 } })
  const district = page.getByTestId('district-detail').last()
  await expect(district).toBeVisible()
  await expect(page).toHaveURL(/[?&]d=\d+/)
  await expect(page).not.toHaveURL(/[?&]sel=/)
  const best = district.getByTestId('district-best').getByTestId('place-card')
  await expect(best.first()).toBeVisible()
  if (!isMobile) {
    // A place opened from the district goes back to the district.
    await best.first().getByRole('button').first().click({ position: { x: 40, y: 24 } })
    await expect(page.getByTestId('detail')).toBeVisible()
    await page.getByTestId('detail-back').click()
    await expect(page.getByTestId('district-detail')).toBeVisible()
    await page.getByTestId('detail-back').click()
    await expect(page.getByTestId('tab-districts')).toBeVisible()
    await expect(page).not.toHaveURL(/[?&]d=/)
  }

  expect(errors, isMobile ? 'mobile' : 'desktop').toEqual([])
})

test('a chosen language survives reload and city choice', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('lang-select').selectOption('cs')
  await expect(page.locator('html')).toHaveAttribute('lang', 'cs')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'cs')
  await page.getByTestId('search-submit').click()
  await expect(page).toHaveURL(/\/krakow/)
  await expect(page.locator('html')).toHaveAttribute('lang', 'cs')
})

test('Korean is picked from the language menu', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('lang-select').selectOption('ko')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ko')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('내 삶에 맞는 동네를 찾아보세요.')
})
