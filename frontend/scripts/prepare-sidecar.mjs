import { execSync } from "node:child_process";
import { copyFileSync, chmodSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const SOURCE_BY_PLATFORM = {
  win32: "litreview-backend-windows.exe",
  darwin: "litreview-backend-macos",
  linux: "litreview-backend-linux",
};

const sourceName = SOURCE_BY_PLATFORM[process.platform];
if (!sourceName) {
  console.error(`Unsupported platform: ${process.platform}`);
  process.exit(1);
}

const sourcePath = join("..", "backend", "dist", sourceName);
if (!existsSync(sourcePath)) {
  console.error(
    `Missing ${sourcePath}. Build the backend first:\n  cd backend && pip install -e ".[dev]" pyinstaller && pyinstaller --distpath dist --workpath build packaging/litreview.spec`
  );
  process.exit(1);
}

const targetTriple = execSync("rustc --print host-tuple").toString().trim();
const extension = process.platform === "win32" ? ".exe" : "";
const destDir = join("src-tauri", "binaries");
mkdirSync(destDir, { recursive: true });
const destPath = join(destDir, `litreview-backend-${targetTriple}${extension}`);

copyFileSync(sourcePath, destPath);
if (process.platform !== "win32") {
  chmodSync(destPath, 0o755);
}
console.log(`Sidecar staged at ${destPath}`);
