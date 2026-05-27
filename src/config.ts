import "dotenv/config";

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing ${name}. Copy .env.example to .env and set your values.`);
  }
  return value;
}

export const config = {
  token: required("FLUXER_TOKEN"),
  prefix: process.env.PREFIX?.trim() || "!",
  apiUrl: process.env.FLUXER_API_URL?.trim() || "https://api.fluxer.app",
};
