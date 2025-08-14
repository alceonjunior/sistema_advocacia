/* gestao/static/gestao/js/calculo_wizard.js */
/* global $, bootstrap */

/* ===========================================================
 * Endpoints – com fallback
 * (pode setar no template via {% url %}):
 *   window.API_INDICES_CATALOGO
 *   window.CALC_ENDPOINT
 * =========================================================== */
const API_INDICES_CATALOGO =
  window.API_INDICES_CATALOGO || "/api/indices/catalogo/";
const CALC_ENDPOINT =
  window.CALC_ENDPOINT || "/ajax/calculo/wizard/calcular/";

/* ===========================================================
 * Estado global
 * =========================================================== */
const $doc = $(document);
let INDICE_CATALOGO = {}; // { id: {id,label,grupo,params?} }
let parcelaSeq = 0;

/* ===========================================================
 * Utilitários de máscara
 * =========================================================== */
function applyCurrencyMask($inputs) {
  try {
    $inputs.filter('input[type="text"]').mask("#.##0,00", { reverse: true });
  } catch (_) {}
}
function applyDateMask($inputs) {
  try {
    $inputs.filter('input[type="text"]').mask("00/00/0000");
  } catch (_) {}
}
function refreshMasks($root) {
  const $scope = $root && $root.length ? $root : $(document);
  applyCurrencyMask($scope.find("input.parcela-valor"));
  applyDateMask($scope.find("input.parcela-data"));
  applyDateMask($scope.find("input.dt-inicio"));
  applyDateMask($scope.find("input.dt-fim"));
  applyCurrencyMask($scope.find("input.juros-taxa-mensal"));
}

/* ===========================================================
 * Datas – helpers
 * =========================================================== */
function toBRDate(v) {
  if (!v) return "";
  const s = String(v).trim();
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(s)) return s;
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  return s;
}
function parseDateBR(s) {
  const m = String(s || "").match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!m) return null;
  const d = new Date(+m[3], +m[2] - 1, +m[1]);
  return isNaN(d.getTime()) ? null : d;
}
function formatDateBR(d) {
  if (!(d instanceof Date) || isNaN(d.getTime())) return "";
  const DD = String(d.getDate()).padStart(2, "0");
  const MM = String(d.getMonth() + 1).padStart(2, "0");
  const YYYY = d.getFullYear();
  return `${DD}/${MM}/${YYYY}`;
}
function addMonths(d, n) {
  const x = new Date(d.getTime());
  const dom = x.getDate();
  x.setMonth(x.getMonth() + n);
  if (x.getDate() < dom) x.setDate(0);
  return x;
}
function addYears(d, n) {
  const x = new Date(d.getTime());
  x.setFullYear(x.getFullYear() + n);
  return x;
}

/* ===========================================================
 * UI helpers (placeholder, contadores e botão Next/Calcular)
 * =========================================================== */
function togglePlaceholder() {
  const has = $("#parcelas-container .parcela-card").length > 0;
  $("#parcelas-placeholder").toggle(!has);
}

function findStepLinkByText(keyword) {
  keyword = (keyword || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
  let $links = $('.nav-link[data-bs-toggle="tab"], .nav-link[data-bs-toggle="pill"]');
  if (!$links.length) $links = $(".nav .nav-link");
  const $match = $links.filter(function () {
    const t = $(this).text().normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
    return t.includes(keyword);
  });
  return $match.first();
}

function ensureCountPill($link) {
  if (!$link.length) return null;
  let $pill = $link.find(".count-pill");
  if (!$pill.length) {
    $pill = $('<span class="badge bg-secondary ms-2 count-pill"></span>');
    $link.append($pill);
  }
  return $pill;
}

function updateWizardCounters() {
  const qtdParcelas = $("#parcelas-container .parcela-card").length;
  // Aba "Parcelas"
  const $linkParcelas = findStepLinkByText("parcelas");
  ensureCountPill($linkParcelas)?.text(qtdParcelas);

  // Aba "Extras": se desejar exibir algo, é aqui (ex.: 2/3 marcados)
  // Por ora deixamos sem contador (evita poluir).
}

function reindexParcelas() {
  $("#parcelas-container .parcela-card").each(function (i) {
    const idx = i + 1;
    $(this).attr("id", `parcela-${idx}`).attr("data-idx", idx);
    $(this).find(".parcela-title").text(`Parcela ${idx}`);
  });

  // Sidebar
  const $side = $("#parcelas-sidebar").empty();
  $("#parcelas-container .parcela-card").each(function (i) {
    const idx = i + 1;
    const desc =
      ($(this).find(".parcela-descricao").val() || `Parcela ${idx}`).trim() ||
      `Parcela ${idx}`;
    const $item = $(`
      <a href="#parcela-${idx}"
         class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
        <span class="sidebar-label text-truncate">${desc}</span>
        <span class="badge bg-secondary rounded-pill">${idx}</span>
      </a>`);
    $item.on("click", (e) => {
      e.preventDefault();
      document
        .querySelector(`#parcela-${idx}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $side.append($item);
  });

  updateWizardCounters();
  syncNextButtonMode(); // pode estar no passo resultado
}

function setNextButton(mode /* 'next' | 'calcular' */) {
  const $btn = $("#btn-next, .btn-proximo").first();
  if (!$btn.length) return;

  if (mode === "calcular") {
    $btn
      .attr("data-mode", "calcular")
      .removeClass("btn-primary").addClass("btn-success")
      .html('Calcular <i class="bi bi-calculator ms-2"></i>');
  } else {
    $btn
      .attr("data-mode", "next")
      .removeClass("btn-success").addClass("btn-primary")
      .html('Próximo <i class="bi bi-arrow-right ms-2"></i>');
  }
}

function isOnLastStep() {
  // Por abas
  const $links = $('.nav-link[data-bs-toggle="tab"], .nav-link[data-bs-toggle="pill"]');
  if ($links.length) {
    const $act = $links.filter(".active").first();
    const idx = $links.index($act);
    return idx === $links.length - 1;
  }
  // Por divs
  const $steps = getStepDivs();
  if ($steps.length) {
    let $cur = $steps.filter(":visible").first();
    if (!$cur.length) $cur = $steps.filter(".active").first();
    if (!$cur.length) $cur = $steps.first();
    const idx = $steps.index($cur);
    return idx === $steps.length - 1;
  }
  return false;
}

function syncNextButtonMode() {
  setNextButton(isOnLastStep() ? "calcular" : "next");
}

function atualizarUIJuros($faixa) {
  const modo = $faixa.find(".juros-modo").val() || "simples";
  const $simp = $faixa.find(".grupo-juros-simples");
  const $ind = $faixa.find(".grupo-juros-indice");
  if (modo === "por_indice") {
    $simp.addClass("d-none");
    $ind.removeClass("d-none");
  } else {
    $ind.addClass("d-none");
    $simp.removeClass("d-none");
  }
}

/* ===========================================================
 * ÍNDICES – normalização robusta
 * =========================================================== */
function normalizeCatalog(raw) {
  const map = {};

  function ensureParams(p) {
    const params = { ...(p || {}) };
    if (params.code != null && params.serie_id == null) params.serie_id = params.code;
    if (params.serie_id != null && params.code == null) params.code = params.serie_id;
    return params;
  }

  function pushItem(it, groupHint) {
    if (!it) return;
    const id = it.id ?? it.key ?? it.codigo ?? it.slug ?? it.name ?? it.label;
    if (!id) return;
    const label = it.label ?? it.nome ?? it.name ?? it.descricao ?? String(id);
    const grupo = it.grupo ?? it.categoria ?? it.group ?? groupHint ?? "Outros";
    map[id] = { ...it, id, label, grupo, params: ensureParams(it.params) };
  }

  function walk(obj, groupHint) {
    if (!obj) return;

    if (Array.isArray(obj)) {
      obj.forEach((x) => pushItem(x, groupHint));
      return;
    }

    if (typeof obj === "object") {
      if (obj.indices) return walk(obj.indices, groupHint);
      if (obj.catalogo) return walk(obj.catalogo, groupHint);
      if (obj.catalog) return walk(obj.catalog, groupHint);
      if (obj.data) return walk(obj.data, groupHint);

      if (Array.isArray(obj.grupos) || Array.isArray(obj.groups)) {
        (obj.grupos || obj.groups).forEach((g) => {
          const gName = g.nome || g.label || g.name || groupHint || "Outros";
          const itens = g.itens || g.items || g.indices || [];
          walk(itens, gName);
        });
        return;
      }

      Object.entries(obj).forEach(([k, v]) => {
        if (v && typeof v === "object") {
          if (
            v.params != null ||
            v.label != null ||
            v.nome != null ||
            v.name != null ||
            v.codigo != null ||
            v.type != null
          ) {
            pushItem({ id: v.id ?? k, ...v }, groupHint);
          } else {
            walk(v, groupHint);
          }
        }
      });
    }
  }

  walk(raw, "Outros");
  return map;
}

async function carregarCatalogoIndices() {
  try {
    const resp = await fetch(API_INDICES_CATALOGO, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    INDICE_CATALOGO = normalizeCatalog(json);
  } catch (e) {
    console.warn("Falha ao carregar catálogo de índices.", e);
    INDICE_CATALOGO = {};
  }
}

function popularSelectIndice($select) {
  if (!$select || !$select.length) return;
  const prev = $select.val();
  $select.empty();

  const grupos = {};
  Object.values(INDICE_CATALOGO).forEach((meta) => {
    const g = meta.grupo || "Outros";
    (grupos[g] ||= []).push({ id: meta.id, label: meta.label || meta.id });
  });

  $select.append(new Option("Selecione...", "", true, false));

  const gNames = Object.keys(grupos).sort((a, b) =>
    a.localeCompare(b, "pt-BR")
  );
  gNames.forEach((g) => {
    const items = grupos[g].sort((a, b) =>
      a.label.localeCompare(b.label, "pt-BR")
    );
    if (gNames.length === 1) {
      items.forEach((it) =>
        $select.append(new Option(it.label, it.id, false, false))
      );
    } else {
      const $og = $(`<optgroup label="${g}"></optgroup>`);
      items.forEach((it) =>
        $og.append(new Option(it.label, it.id, false, false))
      );
      $select.append($og);
    }
  });

  if (prev && $select.find(`option[value="${prev}"]`).length) $select.val(prev);
  else $select.val("");
}

function repopularTodosSelectsIndice() {
  $(".select-indice-correcao, .select-indice-juros").each(function () {
    popularSelectIndice($(this));
  });
}

/* ===========================================================
 * Templates de Parcela e Faixa
 * =========================================================== */
function tplParcela() {
  parcelaSeq += 1;
  const idx = parcelaSeq;
  return $(`
    <div class="card shadow-sm mb-4 parcela-card" id="parcela-${idx}" data-idx="${idx}">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0 parcela-title">Parcela ${idx}</h5>
        <div class="btn-group btn-group-sm">
          <button type="button" class="btn btn-outline-primary btn-dup-parcela" title="Duplicar"><i class="bi bi-files"></i></button>
          <button type="button" class="btn btn-outline-danger btn-del-parcela" title="Excluir"><i class="bi bi-trash"></i></button>
        </div>
      </div>
      <div class="card-body">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Descrição</label>
            <input type="text" class="form-control parcela-descricao" placeholder="Ex.: Parcela principal">
          </div>
          <div class="col-md-3">
            <label class="form-label">Valor Original <span class="text-danger">*</span></label>
            <input type="text" class="form-control parcela-valor" placeholder="R$ 0,00">
          </div>
          <div class="col-md-3">
            <label class="form-label">Data do Valor <span class="text-danger">*</span></label>
            <div class="input-group">
              <input type="text" class="form-control parcela-data" placeholder="dd/mm/aaaa">
              <span class="input-group-text"><i class="bi bi-calendar-event"></i></span>
            </div>
          </div>
        </div>

        <hr class="my-4">

        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0">Faixas de Correção e Juros</h6>
          <button type="button" class="btn btn-success btn-sm btn-add-faixa"><i class="bi bi-plus-circle"></i> Adicionar Faixa de Cálculo</button>
        </div>

        <div class="faixas-container"></div>
      </div>
    </div>
  `);
}

function tplFaixa() {
  return $(`
    <div class="card mb-3 faixa-card">
      <div class="card-body">
        <div class="row g-3 align-items-end">
          <div class="col-md-3">
            <label class="form-label">Início</label>
            <input type="text" class="form-control dt-inicio" placeholder="dd/mm/aaaa">
          </div>
          <div class="col-md-3">
            <label class="form-label">Fim</label>
            <input type="text" class="form-control dt-fim" placeholder="dd/mm/aaaa">
          </div>
          <div class="col-md-6 text-end">
            <button type="button" class="btn btn-outline-danger btn-sm btn-del-faixa"><i class="bi bi-trash"></i> Remover Faixa</button>
          </div>
        </div>

        <div class="row g-3 mt-1">
          <div class="col-md-6">
            <label class="form-label">Correção Monetária (Índice)</label>
            <select class="form-select select-indice-correcao"></select>
          </div>
          <div class="col-md-6">
            <label class="form-label">Juros</label>
            <div class="input-group">
              <select class="form-select juros-modo" style="max-width: 180px;">
                <option value="simples">Simples (a.m.)</option>
                <option value="por_indice">Por Índice</option>
              </select>
              <div class="flex-grow-1 ps-2 grupo-juros-simples">
                <input type="text" class="form-control juros-taxa-mensal" placeholder="% a.m. (ex.: 1,00)">
              </div>
              <div class="flex-grow-1 ps-2 d-none grupo-juros-indice">
                <select class="form-select select-indice-juros"></select>
              </div>
              <select class="form-select ms-2 juros-capitalizacao" style="max-width: 160px;">
                <option value="">Sem Capitalização</option>
                <option value="mensal">Capitalização Mensal</option>
                <option value="anual">Capitalização Anual</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  `);
}

/* ===========================================================
 * CRUD de parcelas / faixas
 * =========================================================== */
function addFaixa($parcela) {
  const $fx = tplFaixa();
  $parcela.find(".faixas-container").append($fx);
  popularSelectIndice($fx.find(".select-indice-correcao"));
  popularSelectIndice($fx.find(".select-indice-juros"));
  refreshMasks($fx);
  atualizarUIJuros($fx);
  return $fx;
}

function addParcela(prefill) {
  const $p = tplParcela();
  $("#parcelas-container").append($p);
  togglePlaceholder();
  reindexParcelas();
  refreshMasks($p);

  let $f = addFaixa($p);

  if (prefill) {
    if (prefill.descricao) $p.find(".parcela-descricao").val(prefill.descricao);
    if (prefill.valor) $p.find(".parcela-valor").val(prefill.valor);
    if (prefill.data) $p.find(".parcela-data").val(toBRDate(prefill.data));
    if (Array.isArray(prefill.fases)) {
      $p.find(".faixa-card").remove();
      prefill.fases.forEach((fx) => {
        $f = addFaixa($p);
        if (fx.inicio) $f.find(".dt-inicio").val(toBRDate(fx.inicio));
        if (fx.fim) $f.find(".dt-fim").val(toBRDate(fx.fim));
        if (fx.correcao_id)
          $f.find(".select-indice-correcao").val(fx.correcao_id).trigger("change");

        if (fx.juros_modo === "simples") {
          $f.find(".juros-modo").val("simples").trigger("change");
          if (fx.taxa_mensal) $f.find(".juros-taxa-mensal").val(fx.taxa_mensal);
        } else {
          $f.find(".juros-modo").val("por_indice").trigger("change");
          if (fx.juros_id)
            $f.find(".select-indice-juros").val(fx.juros_id).trigger("change");
        }
        if (fx.capitalizacao)
          $f.find(".juros-capitalizacao").val(fx.capitalizacao);
      });
    }
  }
  updateWizardCounters();
  return $p;
}

function removerParcela($parcela) {
  if ($("#parcelas-container .parcela-card").length <= 1) {
    alert("É necessário manter ao menos uma parcela.");
    return;
  }
  $parcela.remove();
  reindexParcelas();
  togglePlaceholder();
}

function duplicarParcela($parcela) {
  const prefill = {
    descricao: $parcela.find(".parcela-descricao").val(),
    valor: $parcela.find(".parcela-valor").val(),
    data: toBRDate($parcela.find(".parcela-data").val()),
    fases: [],
  };
  $parcela.find(".faixa-card").each(function () {
    const $f = $(this);
    const modo = $f.find(".juros-modo").val() || "simples";
    const fase = {
      inicio: toBRDate($f.find(".dt-inicio").val()),
      fim: toBRDate($f.find(".dt-fim").val()),
      capitalizacao: $f.find(".juros-capitalizacao").val() || null,
    };
    const corrId = $f.find(".select-indice-correcao").val();
    if (corrId) fase.correcao_id = corrId;

    if (modo === "simples") {
      fase.juros_modo = "simples";
      fase.taxa_mensal = $f.find(".juros-taxa-mensal").val() || null;
    } else {
      fase.juros_modo = "por_indice";
      fase.juros_id = $f.find(".select-indice-juros").val() || null;
    }
    prefill.fases.push(fase);
  });
  addParcela(prefill);
}

/* ===========================================================
 * Coleta de dados
 * =========================================================== */
function getValueBySelectors(selectors) {
  for (const sel of selectors) {
    const $el = $(sel);
    if ($el.length) {
      const v = $el.val();
      return sel.includes("data") || sel.includes("dt") ? toBRDate(v) : v;
    }
  }
  return "";
}

function coletarBasicos() {
  return {
    numero_processo: getValueBySelectors([
      "#numero_processo",
      "#num_processo",
      "#numero-processo",
    ]),
    data_transito: toBRDate(
      getValueBySelectors(["#data_transito", "#dt_transito", "#data-transito"])
    ),
    parte_autor: getValueBySelectors(["#parte_autor", "#nome_autor", "#parte-autor"]),
    parte_reu: getValueBySelectors(["#parte_reu", "#nome_reu", "#parte-reu"]),
    observacoes: getValueBySelectors(["#observacoes", "#observacoes_gerais"]),
  };
}

function coletarExtras() {
  return {
    honorarios_percent: getValueBySelectors([
      "#honorarios_percent",
      "#honorarios-percent",
    ]),
    honorarios_sobre: getValueBySelectors([
      "#honorarios_sobre",
      "#honorarios-sobre",
    ]),
    multa_percent: getValueBySelectors(["#multa_percent", "#multa-percent"]),
    multa_sobre: getValueBySelectors(["#multa_sobre", "#multa-sobre"]),
    juros_mora_mensal: getValueBySelectors([
      "#juros_mora_mensal",
      "#juros-mora-mensal",
    ]),
  };
}

function coletarParcelas() {
  const arr = [];
  $("#parcelas-container .parcela-card").each(function () {
    const $p = $(this);
    const item = {
      descricao: $p.find(".parcela-descricao").val(),
      valor: $p.find(".parcela-valor").val(),
      data: toBRDate($p.find(".parcela-data").val()),
      fases: [],
    };

    $p.find(".faixa-card").each(function () {
      const $f = $(this);
      const faixa = {
        inicio: toBRDate($f.find(".dt-inicio").val() || null),
        fim: toBRDate($f.find(".dt-fim").val() || null),
      };

      const corrId = $f.find(".select-indice-correcao").val();
      if (corrId) {
        const meta = INDICE_CATALOGO[corrId] || {};
        faixa.correcao = {
          id: corrId,
          indice_id: corrId,
          indice: $f.find(".select-indice-correcao option:selected").text(),
          params: meta.params || null,
        };
      }

      const modo = $f.find(".juros-modo").val() || "simples";
      if (modo === "simples") {
        faixa.juros = {
          modo: "simples",
          taxa_mensal: $f.find(".juros-taxa-mensal").val() || null,
          capitalizacao: $f.find(".juros-capitalizacao").val() || null,
        };
      } else {
        const jurId = $f.find(".select-indice-juros").val();
        const metaJ = INDICE_CATALOGO[jurId] || {};
        faixa.juros = {
          modo: "por_indice",
          indice: jurId
            ? {
                id: jurId,
                indice_id: jurId,
                indice: $f.find(".select-indice-juros option:selected").text(),
                params: metaJ.params || null,
              }
            : null,
          capitalizacao: $f.find(".juros-capitalizacao").val() || null,
        };
      }

      item.fases.push(faixa);
    });

    arr.push(item);
  });
  return arr;
}

function getCSRFToken() {
  const name = "csrftoken=";
  const parts = (decodeURIComponent(document.cookie || "")).split(";");
  for (let p of parts) {
    p = p.trim();
    if (p.startsWith(name)) return p.substring(name.length);
  }
  return "";
}

function formatNumberBR(v) {
  if (v == null) return "0,00";
  const num =
    typeof v === "string"
      ? parseFloat(v.replace(/\./g, "").replace(",", "."))
      : Number(v);
  if (isNaN(num)) return "0,00";
  return num.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/* ===========================================================
 * Envio do cálculo
 * =========================================================== */
async function enviarCalculo() {
  const payload = {
    basicos: coletarBasicos(),
    parcelas: coletarParcelas(),
    extras: coletarExtras(),
  };

  let resp;
  try {
    resp = await fetch(CALC_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": getCSRFToken(),
      },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    alert("Falha de rede ao calcular. Tente novamente.");
    return;
  }

  if (!resp.ok) {
    let msg = "Falha ao calcular. Verifique os dados.";
    try {
      const j = await resp.json();
      if (j && (j.error || j.message)) msg = j.error || j.message;
    } catch (_) {}
    alert(msg);
    return;
  }

  const data = await resp.json();
  const total = data.total_geral || 0;

  const $out = $("#resultado-resumo");
  if ($out.length) {
    $out
      .removeClass("d-none")
      .html(
        `<div class="alert alert-success mb-0"><strong>Sucesso!</strong> Total Geral: <span class="fw-bold">R$ ${formatNumberBR(
          total
        )}</span></div>`
      );
    document
      .querySelector("#resultado-resumo")
      ?.scrollIntoView({ behavior: "smooth" });
  } else {
    alert(`Cálculo concluído. Total: R$ ${formatNumberBR(total)}`);
  }
}

/* ===========================================================
 * Replicação
 * =========================================================== */
function confirmarReplicacao() {
  const tipo = $("#replicacao-tipo").val() || "simples";
  const qtd = Math.max(1, parseInt($("#replicacao-quantidade").val() || "1", 10));
  const periodo = $("#replicacao-periodo").val() || "mensal";

  const $ult = $("#parcelas-container .parcela-card").last();
  if (!$ult.length) return;

  const baseDesc = $ult.find(".parcela-descricao").val();
  const baseValor = $ult.find(".parcela-valor").val();
  const baseData = toBRDate($ult.find(".parcela-data").val());
  const baseDt = parseDateBR(baseData) || new Date();

  const fasesBase = [];
  $ult.find(".faixa-card").each(function () {
    const $f = $(this);
    const modo = $f.find(".juros-modo").val() || "simples";
    const fase = {
      inicio: toBRDate($f.find(".dt-inicio").val()),
      fim: toBRDate($f.find(".dt-fim").val()),
      capitalizacao: $f.find(".juros-capitalizacao").val() || null,
    };
    const corrId = $f.find(".select-indice-correcao").val();
    if (corrId) fase.correcao_id = corrId;

    if (modo === "simples") {
      fase.juros_modo = "simples";
      fase.taxa_mensal = $f.find(".juros-taxa-mensal").val() || null;
    } else {
      fase.juros_modo = "por_indice";
      fase.juros_id = $f.find(".select-indice-juros").val() || null;
    }
    fasesBase.push(fase);
  });

  for (let i = 1; i <= qtd; i++) {
    let dataStr = baseData;
    if (tipo === "sucessiva") {
      const next = periodo === "anual" ? addYears(baseDt, i) : addMonths(baseDt, i);
      dataStr = formatDateBR(next);
    }
    addParcela({
      descricao: baseDesc,
      valor: baseValor,
      data: dataStr,
      fases: fasesBase,
    });
  }

  try {
    $("#modalReplicacao").modal("hide");
  } catch (_) {}
}

/* ===========================================================
 * Navegação (abas e fallback em divs)
 * =========================================================== */
function getTabLinks() {
  return $('.nav-link[data-bs-toggle="tab"], .nav-link[data-bs-toggle="pill"]');
}
function showTab($link) {
  if (!$link || !$link.length) return;
  try {
    const tab = bootstrap.Tab.getOrCreateInstance($link[0]);
    tab.show();
    const target = $link.attr("data-bs-target") || $link.attr("href");
    if (target && target.startsWith("#")) {
      document
        .querySelector(target)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
      history.replaceState(null, "", target);
    }
    syncNextButtonMode();
  } catch (_) {}
}
function gotoNextTab() {
  const $links = getTabLinks();
  if (!$links.length) return false;
  const $act = $links.filter(".active").first();
  const idx = $links.index($act);
  if (idx > -1 && idx < $links.length - 1) showTab($links.eq(idx + 1));
  return true;
}
function gotoPrevTab() {
  const $links = getTabLinks();
  if (!$links.length) return false;
  const $act = $links.filter(".active").first();
  const idx = $links.index($act);
  if (idx > 0) showTab($links.eq(idx - 1));
  return true;
}
function getStepDivs() {
  let $s = $(".wizard-step");
  if ($s.length) return $s;
  $s = $(".step-pane");
  if ($s.length) return $s;
  $s = $('[id^="step-"][data-step]');
  if ($s.length) return $s;
  return $('[id^="step-"]');
}
function gotoNextDiv() {
  const $s = getStepDivs();
  if (!$s.length) return false;
  let $c = $s.filter(":visible").first();
  if (!$c.length) $c = $s.filter(".active").first();
  if (!$c.length) $c = $s.first();
  const i = $s.index($c);
  if (i > -1 && i < $s.length - 1) {
    $c.addClass("d-none").removeClass("active");
    const $n = $s.eq(i + 1).removeClass("d-none").addClass("active");
    $n[0]?.scrollIntoView({ behavior: "smooth", block: "start" });
    syncNextButtonMode();
    return true;
  }
  return false;
}
function gotoPrevDiv() {
  const $s = getStepDivs();
  if (!$s.length) return false;
  let $c = $s.filter(":visible").first();
  if (!$c.length) $c = $s.filter(".active").first();
  if (!$c.length) $c = $s.first();
  const i = $s.index($c);
  if (i > 0) {
    $c.addClass("d-none").removeClass("active");
    const $p = $s.eq(i - 1).removeClass("d-none").addClass("active");
    $p[0]?.scrollIntoView({ behavior: "smooth", block: "start" });
    syncNextButtonMode();
    return true;
  }
  return false;
}

/* ===========================================================
 * Inicialização
 * =========================================================== */
$(async function () {
  // 1) Catálogo e selects
  await carregarCatalogoIndices();
  repopularTodosSelectsIndice();

  // 2) Contadores iniciais e botão Next
  updateWizardCounters();
  syncNextButtonMode();

  // 3) Eventos de abas (quando o usuário navega pelo topo)
  $doc.on("shown.bs.tab", '.nav-link[data-bs-toggle="tab"], .nav-link[data-bs-toggle="pill"]', function () {
    syncNextButtonMode();
  });

  // 4) Botões globais
  $doc.on("click", "#btn-add-parcela", function (e) {
    e.preventDefault();
    addParcela();
  });

  $doc.on("click", "#btn-update-all-today", function (e) {
    e.preventDefault();
    const hoje = formatDateBR(new Date());
    $("#parcelas-container .parcela-data").each(function () {
      $(this).val(hoje);
    });
  });

  $doc.on("click", "#btn-confirmar-replicacao", function (e) {
    e.preventDefault();
    confirmarReplicacao();
  });

  // Next / Prev – com detecção de modo "calcular"
  $doc.on(
    "click",
    '[data-wizard="next"], .btn-next, #btn-next, #btn-proximo, .btn-proximo',
    function (e) {
      e.preventDefault();
      const mode = $(this).attr("data-mode");
      if (mode === "calcular" || isOnLastStep()) {
        enviarCalculo();
      } else {
        if (!gotoNextTab()) gotoNextDiv();
      }
    }
  );

  $doc.on(
    "click",
    '[data-wizard="prev"], .btn-prev, #btn-prev, #btn-anterior, .btn-anterior',
    function (e) {
      e.preventDefault();
      if (!gotoPrevTab()) gotoPrevDiv();
      syncNextButtonMode();
    }
  );

  // 5) Delegação de eventos dinâmicos (cards/faixas)
  $doc.on("click", ".btn-del-parcela", function () {
    removerParcela($(this).closest(".parcela-card"));
  });
  $doc.on("click", ".btn-dup-parcela", function () {
    duplicarParcela($(this).closest(".parcela-card"));
  });
  $doc.on("click", ".btn-add-faixa", function () {
    addFaixa($(this).closest(".parcela-card"));
  });
  $doc.on("click", ".btn-del-faixa", function () {
    $(this).closest(".faixa-card").remove();
  });
  $doc.on("change", ".juros-modo", function () {
    atualizarUIJuros($(this).closest(".faixa-card"));
  });
  $doc.on("input", ".parcela-descricao", function () {
    reindexParcelas();
  });

  // 6) Garante pelo menos 1 parcela
  if ($("#parcelas-container .parcela-card").length === 0) {
    addParcela();
  } else {
    reindexParcelas();
    refreshMasks($("#parcelas-container"));
  }
  togglePlaceholder();
});
