import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { expect, test } from '@playwright/test';

const E2E_DIR = path.join(os.tmpdir(), 'compulsa_e2e');
const OUTBOX_FILE = path.join(E2E_DIR, 'email_outbox.jsonl');

interface OutboxRecord {
  recipient: string;
  verification_token: string;
}

async function waitForVerificationToken(email: string): Promise<string> {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    if (fs.existsSync(OUTBOX_FILE)) {
      const lines = fs
        .readFileSync(OUTBOX_FILE, 'utf-8')
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
      for (let i = lines.length - 1; i >= 0; i--) {
        const parsed = JSON.parse(lines[i]) as OutboxRecord;
        if (parsed.recipient === email && parsed.verification_token) {
          return parsed.verification_token;
        }
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`No llegó token de verificación en ${OUTBOX_FILE} para ${email}`);
}

test('flujo E2E completo: registro, verificación, catálogo CSV, HITL, compulsa, lock-budget, PDF, vista pública y tracción', async ({
  page,
  context,
}) => {
  const uniqueSuffix = Date.now().toString(36);
  const email = `e2e_${uniqueSuffix}@constructora.com.ar`;
  const vendorName = `Corralón Playwright ${uniqueSuffix}`;
  const csvPath = path.join(E2E_DIR, `catalogo_${uniqueSuffix}.csv`);
  fs.mkdirSync(E2E_DIR, { recursive: true });
  fs.writeFileSync(
    csvPath,
    [
      'sku,descripcion,precio_contado,precio_lista,unidad,marca,categoria',
      'PW-H8,Barra Hierro Aletado 8 mm x 12 m,9800,10800,BARRA,Acindar,Acero',
      'PW-PVC34,Caño de 3/4 PVC,4200,4600,UN,Tigre,Plomeria',
      'PW-CEM,Cemento Portland 50 kg,9400,10400,BOLSA,Loma Negra,Obra Gruesa',
      'PW-PVC110,Caño PVC 110 mm x 4 m,17500,19200,UN,Tigre,Plomeria',
    ].join('\n'),
    'utf-8',
  );

  await page.goto('/');

  // 1. Sesión Demo inicial -> Abrir modal de Auth -> Registro Real con verificación por correo (H-28, H-29, H-33)
  await expect(page.getByRole('button', { name: 'Acceder' })).toBeVisible();
  await page.getByRole('button', { name: 'Acceder' }).click();

  await page.getByRole('button', { name: '¿No tienes cuenta? Regístrate gratis' }).click();
  await page.getByPlaceholder('Ej. Ing. Juan Pérez').fill('Ing. Playwright E2E');
  await page.getByPlaceholder('Ej. Pérez & Asoc. Construcciones').fill('Obra Playwright SA');
  await page.getByPlaceholder('juan@constructora.com').fill(email);
  await page.getByPlaceholder('••••••••').fill('PlaywrightPass2026!');
  await page.getByRole('button', { name: 'Crear Cuenta y Enviar Verificación' }).click();

  await expect(page.getByText('Verificar Correo Electrónico')).toBeVisible();

  // Cero tokens JWT expuestos en localStorage (H-21, H-33)
  const storedJwt = await page.evaluate(() => localStorage.getItem('compulsa_access_token'));
  expect(storedJwt).toBeNull();

  const verificationToken = await waitForVerificationToken(email);
  await page.getByPlaceholder('Pegá el código recibido por correo').fill(verificationToken);
  await page.getByRole('button', { name: 'Confirmar Correo y Entrar' }).click();

  // Sesión verificada con cookies HttpOnly + CSRF (H-21, H-33)
  await expect(page.getByText('Obra Playwright SA')).toBeVisible();
  const cookies = await context.cookies();
  const accessCookie = cookies.find((c) => c.name === 'compulsa_access_token');
  const csrfCookie = cookies.find((c) => c.name === 'compulsa_csrf_token');
  expect(accessCookie).toBeDefined();
  expect(accessCookie?.httpOnly).toBe(true);
  expect(csrfCookie).toBeDefined();

  // Probar Logout -> Login por cookies
  await page.getByRole('button', { name: /Salir/i }).click();
  await page.getByRole('button', { name: 'Acceder' }).click();
  await page.getByPlaceholder('juan@constructora.com').fill(email);
  await page.getByPlaceholder('••••••••').fill('PlaywrightPass2026!');
  await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
  await expect(page.getByText('Obra Playwright SA')).toBeVisible();

  // 2. Registrar corralón propio e importar CSV
  await page.getByRole('button', { name: /Gestionar Corralones/i }).click();
  await page.getByRole('tab', { name: /\+ Registrar Nuevo Corralón/i }).click();
  await page.getByPlaceholder('Ej. Corralón Norte Jujuy').fill(vendorName);
  await page.getByRole('button', { name: 'Guardar Corralón' }).click();

  await expect(page.getByText(/Importar Lista de Precios/i)).toBeVisible();
  await page.locator('input[type="file"][accept*=".csv"]').setInputFiles(csvPath);
  await page.getByRole('button', { name: 'Importar Lista' }).click();
  await expect(page.getByText(/¡Catálogo Versión 1 Importado con Éxito!/i)).toBeVisible();
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click();

  // 3. Ingestar Preset 2 (Guardia HITL: "20 barra del 8 y 4 caño de 3/4")
  await page.getByRole('button', { name: /Manuscrito de Obra \(Guardia HITL\)/i }).click();
  await expect(page.getByText(/requiere.*definir material/i)).toBeVisible();

  // Resolver ambigüedad dimensional en UI
  await page.getByRole('button', { name: 'PVC Cloacal / Agua' }).click();
  await expect(page.getByText(/Pliego Completo/i)).toBeVisible();

  // 4. Ejecutar compulsa y congelar presupuesto (H-02, H-31, H-32)
  await page.getByRole('button', { name: 'Ejecutar Compulsa Multi-Corralón' }).click();
  await expect(page.getByRole('button', { name: 'Congelar Presupuesto Definitivo (Lock-Budget)' })).toBeVisible();

  const lockRespPromise = page.waitForResponse(
    (resp) => resp.url().includes('/lock-budget') && resp.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Congelar Presupuesto Definitivo (Lock-Budget)' }).click();
  const lockResp = await lockRespPromise;
  expect(lockResp.status()).toBe(200);
  const lockData = (await lockResp.json()) as { public_share_token: string };
  expect(lockData.public_share_token).toBeTruthy();

  await expect(page.getByText(/Copiar Enlace Público/i)).toBeVisible();

  // 5. Descargar PDF autenticado (H-05)
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'PDF Cliente' }).click();
  const download = await downloadPromise;
  const pdfPath = await download.path();
  expect(pdfPath).toBeTruthy();
  const pdfHeader = fs.readFileSync(pdfPath!).subarray(0, 5).toString('ascii');
  expect(pdfHeader).toBe('%PDF-');

  // 6. Abrir enlace público sellado (/p/:token) y validar privacidad comercial (H-03, H-04, H-32)
  await page.goto(`/p/${lockData.public_share_token}`);
  await expect(page.getByText('Snapshot Inmutable HMAC-SHA256 Verificado')).toBeVisible();
  const publicContent = await page.textContent('body');
  expect(publicContent).not.toContain(vendorName);

  // 7. Validar métricas auditadas en /traccion (H-23, H-30)
  await page.goto('/traccion');
  await expect(page.getByText('Tablero Público Auditable')).toBeVisible();
  await expect(page.getByText(/1 usuario\(s\) reales verificados/i)).toBeVisible();
  await expect(page.getByText(/Compulsas congeladas \(/i)).toBeVisible();
  await expect(page.getByText('Obra Playwright SA')).toHaveCount(0);
});
