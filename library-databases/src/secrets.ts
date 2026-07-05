/**
 * Cross-platform NYPL credential provider.
 *
 * Resolution order (first hit wins):
 *   1. Env vars STATISTA_BARCODE / STATISTA_PIN  → the server path (pensi/Linux)
 *   2. macOS Keychain (service = STATISTA_KEYCHAIN_SERVICE or default)
 *
 * The secret is returned to the caller in memory only — never logged.
 */

export interface Credentials {
  account: string; // NYPL barcode → j_username
  secret: string; // NYPL PIN → j_password
}

const DEFAULT_KEYCHAIN_SERVICE = "shibboleth.nypl.org";

async function fromKeychain(service: string): Promise<Credentials | null> {
  if (Deno.build.os !== "darwin") return null;
  try {
    const attr = await new Deno.Command("security", {
      args: ["find-generic-password", "-s", service],
      stdout: "piped",
      stderr: "null",
    }).output();
    if (!attr.success) return null;
    const account =
      new TextDecoder().decode(attr.stdout).match(/"acct"<blob>="([^"]*)"/)
        ?.[1] ?? "";

    const pw = await new Deno.Command("security", {
      args: ["find-generic-password", "-s", service, "-w"],
      stdout: "piped",
      stderr: "null",
    }).output();
    if (!pw.success) return null;
    const secret = new TextDecoder().decode(pw.stdout).replace(/\r?\n$/, "");
    if (!account || !secret) return null;
    return { account, secret };
  } catch {
    return null;
  }
}

export async function getCredentials(): Promise<Credentials> {
  const envAccount = Deno.env.get("STATISTA_BARCODE");
  const envSecret = Deno.env.get("STATISTA_PIN");
  if (envAccount && envSecret) {
    return { account: envAccount, secret: envSecret };
  }

  const service = Deno.env.get("STATISTA_KEYCHAIN_SERVICE") ??
    DEFAULT_KEYCHAIN_SERVICE;
  const kc = await fromKeychain(service);
  if (kc) return kc;

  throw new Error(
    "No NYPL credentials found. Set STATISTA_BARCODE + STATISTA_PIN env vars " +
      `(Linux/server) or store them in the macOS Keychain under service "${service}".`,
  );
}
