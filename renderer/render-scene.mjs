import { bundle } from "@remotion/bundler";
import { ensureBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index === -1 || !process.argv[index + 1]) {
    throw new Error(`Missing ${name}`);
  }
  return process.argv[index + 1];
}

const propsPath = argument("--props");
const outPath = argument("--out");
const bundleDir = argument("--bundle");
const version = argument("--version");
const progressPath = process.argv.includes("--progress") ? argument("--progress") : null;
const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf8"));
const assetServer = await servePropsAssets(inputProps);
const servedProps = assetServer.props;

await ensureBrowser();

const marker = path.join(bundleDir, ".renderer-version");
let serveUrl = bundleDir;
if (!fs.existsSync(marker) || fs.readFileSync(marker, "utf8").trim() !== version) {
  fs.rmSync(bundleDir, { recursive: true, force: true });
  fs.mkdirSync(bundleDir, { recursive: true });
  serveUrl = await bundle({
    entryPoint: path.join(__dirname, "src", "index.ts"),
    outDir: bundleDir,
  });
  fs.writeFileSync(path.join(serveUrl, ".renderer-version"), version);
}

try {
  const composition = await selectComposition({
    serveUrl,
    id: "Scene",
    inputProps: servedProps,
  });

  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    outputLocation: outPath,
    inputProps: servedProps,
    crf: servedProps.render?.crf ?? 18,
    pixelFormat: "yuv420p",
    colorSpace: "bt709",
    overwrite: true,
    onProgress: ({ progress }) => {
      if (progressPath) {
        fs.writeFileSync(progressPath, String(progress));
      }
    },
  });
} finally {
  await assetServer.close();
}

function collectFiles(value, files) {
  if (typeof value === "string" && value.length > 2 && fs.existsSync(value)) {
    const stat = fs.statSync(value);
    if (stat.isFile()) {
      files.add(path.resolve(value));
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectFiles(item, files));
    return;
  }
  if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectFiles(item, files));
  }
}

function rewrite(value, map) {
  if (typeof value === "string" && map.has(path.resolve(value))) {
    return map.get(path.resolve(value));
  }
  if (Array.isArray(value)) {
    return value.map((item) => rewrite(item, map));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, rewrite(item, map)]));
  }
  return value;
}

function servePropsAssets(props) {
  const files = new Set();
  collectFiles(props, files);
  const idToPath = new Map();
  const pathToUrl = new Map();
  let index = 0;
  for (const file of files) {
    const id = `asset-${index}${path.extname(file)}`;
    index += 1;
    idToPath.set(id, file);
  }
  const server = http.createServer((request, response) => {
    const id = decodeURIComponent((request.url || "/").slice(1).split("?")[0]);
    const file = idToPath.get(id);
    if (!file) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200);
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      for (const [id, file] of idToPath) {
        pathToUrl.set(file, `http://127.0.0.1:${port}/${id}`);
      }
      resolve({
        props: rewrite(props, pathToUrl),
        close: () =>
          new Promise((done) => {
            server.close(() => done());
          }),
      });
    });
  });
}
