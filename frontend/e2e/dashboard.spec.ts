import { expect,test,type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'

async function ready(page:Page){await page.goto('/');await expect(page.getByRole('heading',{name:'Track registry'})).toBeVisible();await expect(page.locator('.zone-label')).toHaveCount(8);await expect(page.locator('canvas')).toBeVisible()}
async function seek(page:Page,time:number){await page.getByLabel('Simulation timeline').evaluate((el,value)=>{const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!;setter.call(el,String(value));el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))},time);await expect(page.locator('.time-readout strong')).toHaveText(`T+${Math.floor(time).toString().padStart(3,'0')}`)}
test('real engine, map, assignment boundaries, inspectors, audit, and baseline',async({page,request})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
  await ready(page)
  expect(await page.locator('canvas').evaluate(el=>!!(el as HTMLCanvasElement).getContext('webgl2'))).toBe(true)
  await expect(page.locator('.probability-row')).toHaveCount(8)
  await seek(page,11.9);await expect(page.locator('.assignment-card')).toContainText('Monitoring only')
  await seek(page,12);const assigned=await (await request.get('http://127.0.0.1:8000/api/tracks/T11?time=12')).json();await expect(page.locator('.assignment-card')).toContainText(assigned.assigned_resource)
  await seek(page,40);await expect(page.locator('.assignment-card')).toContainText(assigned.assigned_resource)
  await seek(page,51.9);await expect(page.locator('.assignment-card')).toContainText(assigned.assigned_resource)
  await seek(page,52);await expect(page.locator('.inspector-title')).toContainText('RELEASE');await expect(page.locator('.assignment-card')).toContainText('Monitoring only')
  await page.getByRole('button',{name:'evidence',exact:true}).click();await expect(page.getByText('4/4 CYCLES')).toBeVisible();await page.getByRole('button',{name:'overview',exact:true}).click()
  await page.getByLabel('Open decision audit').click();await expect(page.locator('.audit-drawer')).toContainText('Persistent low-consequence evidence');await expect(page.locator('.audit-drawer')).not.toContainText('T+084');await page.getByLabel('Close audit').click()
  await seek(page,83.9);await page.getByLabel('Inspect T17',{exact:true}).click();await expect(page.locator('.assignment-card')).toContainText('Monitoring only')
  await seek(page,84);const t17=await (await request.get('http://127.0.0.1:8000/api/tracks/T17?time=84')).json();await expect(page.locator('.assignment-card')).toContainText(t17.assigned_resource)
  await page.locator('.assignment-card button').click();await expect(page.locator('.inspector-title')).toContainText(t17.assigned_resource);await expect(page.locator('.inspector')).toContainText('T17')
  await page.locator('.zone-label').filter({hasText:'Open water'}).click();await expect(page.locator('.inspector')).toContainText('Pelagic Expanse');await expect(page.locator('.inspector')).toContainText('LOW CONSEQUENCE ≠ SAFE')
  await page.locator('.site-label').filter({hasText:'S01'}).click();await expect(page.locator('.inspector')).toContainText('STAGING SITE')
  await seek(page,120);await page.getByLabel('Compare allocation policies').click();const metrics=await (await request.get('http://127.0.0.1:8000/api/metrics?time=120')).json();await expect(page.locator('.comparison-panel')).toContainText(`${metrics.swarm.critical_tracks_covered} / ${metrics.high_consequence_tracks}`);await expect(page.locator('.comparison-panel')).toContainText(`${metrics.baseline.critical_tracks_covered} / ${metrics.high_consequence_tracks}`)
  await page.getByLabel('Close comparison').click();await seek(page,40);await page.getByLabel('Inspect T11',{exact:true}).click()
  await mkdir('../artifacts',{recursive:true});await page.screenshot({path:'../artifacts/dashboard-desktop.png',fullPage:true})
  expect(errors).toEqual([])
})
test('playback, orbit, filters, layers, demo and responsive layout',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
  await ready(page);await page.getByLabel('Play simulation',{exact:true}).click();await expect(page.getByLabel('Pause simulation',{exact:true})).toBeVisible();await expect.poll(async()=>Number(await page.getByLabel('Simulation timeline').inputValue())).toBeGreaterThan(.3);await page.getByLabel('Pause simulation',{exact:true}).click()
  await page.getByRole('button',{name:'4×',exact:true}).click();await expect(page.getByRole('button',{name:'4×',exact:true})).toHaveAttribute('aria-pressed','true')
  await seek(page,52);await page.getByLabel('Filter tracks').selectOption('water');await expect(page.getByLabel('Inspect T11',{exact:true})).toBeVisible();await page.getByLabel('Filter tracks').selectOption('assigned');await expect(page.getByLabel('Inspect T11',{exact:true})).toHaveCount(0);await page.getByLabel('Filter tracks').selectOption('all')
  await page.getByLabel('Map layers').click();await page.getByRole('button',{name:'labels',exact:true}).click();await expect(page.locator('.zone-label')).toHaveCount(0);await page.getByRole('button',{name:'labels',exact:true}).click();await page.getByLabel('Map layers').click()
  const canvas=page.locator('canvas'),box=(await canvas.boundingBox())!;await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.5+45,box.y+box.height*.5+20,{steps:8});await page.mouse.up();await page.getByLabel('Reset camera').click()
  await page.getByRole('button',{name:'Demo mode',exact:true}).click();await expect(page.locator('.demo-callout')).toContainText('Scarcity, from the start');await expect(page.getByLabel('Pause simulation',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Exit demo',exact:true}).click();await page.getByLabel('Pause simulation',{exact:true}).click()
  await seek(page,84);await page.setViewportSize({width:390,height:844});await expect(page.locator('.topbar')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await mkdir('../artifacts',{recursive:true});await page.screenshot({path:'../artifacts/dashboard-mobile.png',fullPage:true});expect(errors).toEqual([])
})
test('connection failure shows a recoverable error instead of a blank screen',async({page})=>{
  await page.route('**/api/run',route=>route.fulfill({status:503,body:'Unavailable'}));await page.goto('/');await expect(page.getByRole('heading',{name:'Engine unavailable'})).toBeVisible();await expect(page.getByRole('button',{name:'Retry connection'})).toBeVisible()
})
