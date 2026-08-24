import process from "node:process";
import fs from "node:fs";

const reportPath = process.argv[2];
if (!reportPath) {
  console.error("Usage: node tools/assert_d1_counts.mjs <local-d1-report.json>");
  process.exit(1);
}
const expected = JSON.parse(fs.readFileSync(reportPath, "utf8")).tables;

let input = "";
for await (const chunk of process.stdin) {
  input += chunk;
}

try {
  const payload = JSON.parse(input);
  const result = payload?.[0];
  const row = result?.results?.[0];
  if (!result?.success || !row) {
    throw new Error("Wrangler returned no successful count row");
  }
  const mismatches = Object.entries(expected).filter(
    ([name, value]) => Number(row[name]) !== value,
  );
  if (mismatches.length) {
    throw new Error(
      mismatches
        .map(([name, value]) => `${name}: received ${row[name]}, expected ${value}`)
        .join("; "),
    );
  }
  console.log("Remote D1 row-count verification: PASS");
  for (const [name, value] of Object.entries(expected)) {
    console.log(`  ${name}: ${value.toLocaleString("en-US")}`);
  }
} catch (error) {
  console.error(`Remote D1 row-count verification failed: ${error.message}`);
  process.exitCode = 1;
}
