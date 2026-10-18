# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: demo.spec.ts >> Ripple Production UI End-to-End Suite >> Full Demo Workflow, Assertions, Screenshots, 3D/2D Fallback, and A11y
- Location: e2e/demo.spec.ts:14:3

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: page.goto: net::ERR_ABORTED; maybe frame was detached?
Call log:
  - navigating to "http://localhost:8000/", waiting until "load"

```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import * as fs from 'fs';
  3   | import * as path from 'path';
  4   | 
  5   | test.describe('Ripple Production UI End-to-End Suite', () => {
  6   |   const screenshotsDir = path.resolve('../docs/screenshots');
  7   | 
  8   |   test.beforeAll(() => {
  9   |     if (!fs.existsSync(screenshotsDir)) {
  10  |       fs.mkdirSync(screenshotsDir, { recursive: true });
  11  |     }
  12  |   });
  13  | 
  14  |   test('Full Demo Workflow, Assertions, Screenshots, 3D/2D Fallback, and A11y', async ({ page }) => {
  15  |     const consoleErrors: string[] = [];
  16  |     page.on('response', (resp) => {
  17  |       if (resp.status() >= 400) {
  18  |         console.log(`[HTTP ${resp.status()}] ${resp.url()}`);
  19  |       }
  20  |     });
  21  |     page.on('console', (msg) => {
  22  |       if (msg.type() === 'error') {
  23  |         consoleErrors.push(msg.text());
  24  |       }
  25  |     });
  26  | 
  27  |     // Step 1: Navigate to application root served by FastAPI
> 28  |     await page.goto('http://localhost:8000/');
      |                ^ Error: page.goto: net::ERR_ABORTED; maybe frame was detached?
  29  |     await page.waitForLoadState('networkidle');
  30  | 
  31  |     // Confirm title & basic UI elements
  32  |     await expect(page).toHaveTitle(/RIPPLE/);
  33  |     const brand = page.locator('header').getByText('RIPPLE');
  34  |     await expect(brand).toBeVisible();
  35  | 
  36  |     // Verify Disclaimer and Synthetic data indicators are visible
  37  |     await expect(page.getByText('Synthetic Data')).toBeVisible();
  38  |     await expect(page.getByText('Decision-support only')).toBeVisible();
  39  | 
  40  |     // Capture Screenshot 1: Workspace Overview
  41  |     await page.screenshot({ path: path.join(screenshotsDir, 'workspace_overview.png') });
  42  |     console.log('[E2E PASS] Screenshot 1 captured: workspace_overview.png');
  43  | 
  44  |     // Step 2: Trigger Ripple & capture mid-ripple screenshot
  45  |     const replayBtn = page.getByRole('button', { name: 'Replay Ripple' });
  46  |     await expect(replayBtn).toBeVisible();
  47  |     await replayBtn.click();
  48  |     await page.waitForTimeout(400); // mid-wave
  49  |     await page.screenshot({ path: path.join(screenshotsDir, 'mid_ripple.png') });
  50  |     console.log('[E2E PASS] Screenshot 2 captured: mid_ripple.png');
  51  | 
  52  |     // Step 3: Inspect DEC-CARDIO-001
  53  |     // Toggle 2D view or use keyboard drawer to reliably select node
  54  |     const view2dToggle = page.getByTitle(/Toggle between 3D/);
  55  |     await view2dToggle.click();
  56  |     await page.waitForTimeout(300);
  57  | 
  58  |     const decCardioBtn = page.getByRole('button', { name: /DEC-CARDIO-001/ }).first();
  59  |     await expect(decCardioBtn).toBeVisible();
  60  |     await decCardioBtn.click();
  61  | 
  62  |     // Assert Inspector content
  63  |     const inspector = page.getByTestId('inspector-card');
  64  |     await expect(inspector).toBeVisible();
  65  |     await expect(inspector.getByTestId('inspector-status')).toContainText('at_risk');
  66  |     await expect(inspector.getByText(/Hospital-wide Formulary Adoption/)).toBeVisible();
  67  |     await expect(inspector.getByText(/Cardiology Steering Committee/)).toBeVisible();
  68  |     console.log('[E2E PASS] Inspector verified: DEC-CARDIO-001 flagged at_risk with Steering Committee');
  69  | 
  70  |     // Capture Screenshot 3: Inspector with selected Decision
  71  |     await page.screenshot({ path: path.join(screenshotsDir, 'inspector_decision.png') });
  72  |     console.log('[E2E PASS] Screenshot 3 captured: inspector_decision.png');
  73  | 
  74  |     // Step 4: Ranked Alerts assertion for SYN-REV-001
  75  |     const alertCard = page.getByTestId('alert-card-SYN-REV-001');
  76  |     await expect(alertCard).toBeVisible();
  77  |     await expect(alertCard.getByTestId('alert-reason-category')).toHaveText('fabrication');
  78  |     await expect(alertCard.getByText(/Floor Active/)).toBeVisible();
  79  | 
  80  |     // Verify score >= 0.5
  81  |     const scoreText = await alertCard.getByTestId('alert-score-value').innerText();
  82  |     const parsedScore = parseFloat(scoreText);
  83  |     console.log(`[E2E PASS] SYN-REV-001 Base & Score: ${parsedScore} (verified >= 0.5)`);
  84  |     expect(parsedScore).toBeGreaterThanOrEqual(0.5);
  85  | 
  86  |     // Expand "Why this rank?"
  87  |     const whyBtn = alertCard.getByRole('button', { name: /Why this rank/ });
  88  |     await whyBtn.click();
  89  |     await page.waitForTimeout(400);
  90  |     await expect(page.getByText(/Formula Breakdown/)).toBeVisible();
  91  |     console.log('[E2E PASS] Why this rank expanded: mathematical breakdown confirmed');
  92  | 
  93  |     // Step 5: Coordination Tab & Screenshot 4
  94  |     const coordTabBtn = page.getByRole('button', { name: /Coordination Board/ });
  95  |     await coordTabBtn.click();
  96  |     await page.waitForTimeout(300);
  97  |     await expect(page.getByText('Completed', { exact: true })).toBeVisible();
  98  |     await page.screenshot({ path: path.join(screenshotsDir, 'coordination_tab.png') });
  99  |     console.log('[E2E PASS] Screenshot 4 captured: coordination_tab.png');
  100 | 
  101 |     // Step 6: Load Demo Scenario & Dismiss 3 administrative alerts
  102 |     const loadDemoBtn = page.getByRole('button', { name: /Load Demo/ });
  103 |     await loadDemoBtn.click();
  104 |     await page.waitForTimeout(1200);
  105 | 
  106 |     // Dismiss 3 administrative alerts by exact review card IDs
  107 |     const adm01 = page.locator('[data-testid="alert-card-SYN-REV-ADM-01"]');
  108 |     const adm02 = page.locator('[data-testid="alert-card-SYN-REV-ADM-02"]');
  109 |     const adm03 = page.locator('[data-testid="alert-card-SYN-REV-ADM-03"]');
  110 | 
  111 |     await expect(adm01).toBeVisible({ timeout: 10000 });
  112 |     await adm01.getByRole('button', { name: 'Dismiss' }).click();
  113 |     await page.waitForTimeout(600);
  114 | 
  115 |     await expect(adm02).toBeVisible({ timeout: 5000 });
  116 |     await adm02.getByRole('button', { name: 'Dismiss' }).click();
  117 |     await page.waitForTimeout(600);
  118 | 
  119 |     await expect(adm03).toBeVisible({ timeout: 5000 });
  120 |     await adm03.getByRole('button', { name: 'Dismiss' }).click();
  121 |     await page.waitForTimeout(1500);
  122 | 
  123 |     // Step 7: Memory Tab & Screenshot 5
  124 |     const memoryTabBtn = page.getByRole('button', { name: /Adaptive Memory/ });
  125 |     await memoryTabBtn.click();
  126 |     await page.waitForTimeout(400);
  127 |     await expect(page.getByText('rule_administrative_low', { exact: true })).toBeVisible();
  128 |     console.log('[E2E PASS] Rule rule_administrative_low confirmed in tenant memory');
```