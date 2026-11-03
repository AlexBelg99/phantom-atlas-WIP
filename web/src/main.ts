import { Viewer } from "@photo-sphere-viewer/core";
import "@photo-sphere-viewer/core/index.css";
import "./style.css";

interface Pipeline {
  name: string;
  letter: string;
  label: string;
  description: string;
  endpoints: string[];
  count: number;
  cost_total_usd: number;
}
interface Result {
  file: string;
  cost_usd: number;
  seam_score: number;
  seconds: number;
  raw_size: [number, number];
}
interface Item {
  id: string;
  setting: string;
  surreal: string | null;
  summary: string;
  prompt: string;
  results: Record<string, Result>;
}
interface Index {
  pipelines: Pipeline[];
  items: Item[];
  total_cost_usd: number;
}

const base = import.meta.env.BASE_URL;
const $ = (id: string) => document.getElementById(id)!;

async function start() {
  const index: Index = await fetch(`${base}bakeoff/index.json`).then((r) => r.json());
  let place = 0;
  let pipe = 0;

  // Restore from URL hash, e.g. #p009/gpt_image2
  const [hId, hPipe] = location.hash.slice(1).split("/");
  if (hId) place = Math.max(0, index.items.findIndex((i) => i.id === hId));
  if (hPipe) pipe = Math.max(0, index.pipelines.findIndex((p) => p.name === hPipe));

  const viewer = new Viewer({
    container: $("viewer"),
    navbar: ["zoom", "fullscreen"],
    defaultZoomLvl: 0,
    loadingTxt: "Loading panorama…",
  });

  const url = (r: Result) => `${base}${r.file}`;
  const current = () => index.items[place];
  const currentPipe = () => index.pipelines[pipe];

  function renderPlaces() {
    $("places").innerHTML = index.items
      .map(
        (it, i) =>
          `<button class="place${i === place ? " on" : ""}" data-i="${i}" title="${it.summary}">
             <b>${it.id}</b><span>${it.setting.replace("_", " ")}</span>${it.surreal ? '<i title="surreal">✦</i>' : ""}
           </button>`,
      )
      .join("");
  }

  function renderPipes() {
    const it = current();
    $("pipes").innerHTML = index.pipelines
      .map((p, i) => {
        const r = it.results[p.name];
        return `<button role="tab" class="pipe${i === pipe ? " on" : ""}" data-i="${i}" ${r ? "" : "disabled"}>
                  <span class="letter">${p.letter}</span>
                  <span class="label">${p.label}</span>
                  <span class="meta">${r ? `$${r.cost_usd.toFixed(3)} · seam ${r.seam_score}` : "missing"}</span>
                </button>`;
      })
      .join("");
  }

  function renderDetails() {
    const it = current();
    const p = currentPipe();
    const r = it.results[p.name];
    $("details").innerHTML = `
      ${it.surreal ? `<p class="surreal">✦ Surreal: ${it.surreal}</p>` : ""}
      <p class="summary">${it.summary}</p>
      ${r ? `<dl>
        <dt>Model</dt><dd>${p.description}</dd>
        <dt>Endpoint</dt><dd><code>${p.endpoints.join(" → ")}</code></dd>
        <dt>Raw size</dt><dd>${r.raw_size[0]}×${r.raw_size[1]}</dd>
        <dt>Time</dt><dd>${r.seconds}s</dd>
        <dt>Seam score</dt><dd>${r.seam_score} <small>(edge mismatch, lower is better)</small></dd>
      </dl>` : ""}
      <details><summary>Full prompt</summary><p class="prompt">${it.prompt}</p></details>`;
  }

  function renderFlats() {
    const it = current();
    $("flats").innerHTML = index.pipelines
      .filter((p) => it.results[p.name])
      .map((p) => {
        const i = index.pipelines.indexOf(p);
        return `<figure class="flat${i === pipe ? " on" : ""}" data-i="${i}">
                  <img loading="lazy" src="${url(it.results[p.name])}" alt="${p.label}, ${it.id}" />
                  <figcaption><b>${p.letter}</b> ${p.label}</figcaption>
                </figure>`;
      })
      .join("");
  }

  async function show(keepView: boolean) {
    const r = current().results[currentPipe().name];
    history.replaceState(null, "", `#${current().id}/${currentPipe().name}`);
    renderPlaces();
    renderPipes();
    renderDetails();
    renderFlats();
    if (!r) return;
    await viewer.setPanorama(url(r), {
      // Keep the same viewing angle when switching models, so they can be compared directly.
      ...(keepView ? {} : { position: { yaw: 0, pitch: 0 }, zoom: 0 }),
      transition: false,
      showLoader: true,
    });
  }

  function pickAvailablePipe(dir: 1 | -1) {
    for (let k = 1; k <= index.pipelines.length; k++) {
      const i = (pipe + dir * k + index.pipelines.length) % index.pipelines.length;
      if (current().results[index.pipelines[i].name]) return i;
    }
    return pipe;
  }

  $("places").addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>("[data-i]");
    if (!b) return;
    place = Number(b.dataset.i);
    show(false);
  });
  for (const id of ["pipes", "flats"]) {
    $(id).addEventListener("click", (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>("[data-i]");
      if (!b || (b as HTMLButtonElement).disabled) return;
      pipe = Number(b.dataset.i);
      show(true);
      if (id === "flats") $("viewer").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }
  window.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      pipe = pickAvailablePipe(e.key === "ArrowRight" ? 1 : -1);
      show(true);
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      const n = index.items.length;
      place = (place + (e.key === "ArrowDown" ? 1 : -1) + n) % n;
      show(false);
    } else return;
    e.preventDefault();
  });

  const count = index.pipelines.reduce((s, p) => s + p.count, 0);
  $("footer").innerHTML = `${count} AI-generated panoramas · ${index.items.length} test places ·
    est. API cost $${index.total_cost_usd.toFixed(2)} · all scenes are fictional`;

  show(false);
}

start().catch((err) => {
  $("viewer").innerHTML = `<p class="error">Could not load the bake-off index: ${err}</p>`;
});
