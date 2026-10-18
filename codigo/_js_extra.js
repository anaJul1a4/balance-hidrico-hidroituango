  s_cv(el) {
    const d = D.cv, m = 4600, ink = v("--ink");
    const mk = (y, nm, vis) => ({ type: "scatter", mode: "markers", name: nm, x: d.obs, y: y, text: d.n, visible: vis,
      marker: { size: 7, color: v("--accent"), opacity: .75, line: { color: v("--bg"), width: 1 } },
      hovertemplate: "<b>%{text}</b><br>medida %{x:,.0f} mm · estimada %{y:,.0f} mm<extra></extra>" });
    const tr = [mk(d.kri, "Kriging ordinario", true), mk(d.idw, "IDW p = 1.5", false),
      { type: "scatter", mode: "lines", x: [0, m], y: [0, m], line: { color: ink, width: 1 }, hoverinfo: "skip", showlegend: false }];
    const L = lay({ xaxis: ax("P observada (mm/año)", { range: [0, m] }), yaxis: ax("P estimada sin la estación (mm/año)", { range: [0, m] }),
      margin: { l: 56, r: 12, t: 44, b: 40 } });
    L.updatemenus = [{ type: "buttons", direction: "right", x: 0, xanchor: "left", y: 1.12, yanchor: "top", bgcolor: v("--bg"),
      bordercolor: v("--hair"), font: { size: 11, color: ink }, active: 0, buttons: [
        { label: "Kriging (RMSE 363 mm)", method: "restyle", args: ["visible", [true, false, true]] },
        { label: "IDW p = 1.5 (RMSE 364 mm)", method: "restyle", args: ["visible", [false, true, true]] }] }];
    Plotly.react(el, tr, L, CFG);
  },
  s_coh(el) {
    const d = D.coh, vs = ["Tmax", "Tmed", "Tmin"], col = { Tmax: v("--s1"), Tmed: v("--s2"), Tmin: v("--s3") };
    const tr = vs.map((k, i) => ({ type: "scatter", mode: "markers", name: k, x: d[k + "_obs"], y: d[k + "_mapa"], visible: i === 1,
      customdata: d.n.map((n, j) => [n, d.dz[j]]), marker: { size: 8, color: col[k], line: { color: v("--bg"), width: 1.5 } },
      hovertemplate: `<b>%{customdata[0]}</b><br>${k} medida %{x:.1f} °C · mapa %{y:.1f} °C<br>Z DEM − Z catálogo: %{customdata[1]:+,.0f} m<extra></extra>` }));
    tr.push({ type: "scatter", mode: "lines", x: [0, 36], y: [0, 36], line: { color: v("--ink"), width: 1 }, hoverinfo: "skip" });
    const L = lay({ xaxis: ax("Temperatura medida en la estación (°C)", { range: [0, 36] }), yaxis: ax("Temperatura del mapa (°C)", { range: [-2, 36] }),
      margin: { l: 56, r: 12, t: 44, b: 40 } });
    L.updatemenus = [{ type: "buttons", direction: "right", x: 0, xanchor: "left", y: 1.12, yanchor: "top", bgcolor: v("--bg"),
      bordercolor: v("--hair"), font: { size: 11, color: v("--ink") }, active: 1,
      buttons: vs.map((k, i) => ({ label: k, method: "restyle", args: ["visible", vs.map((_, j) => j === i).concat([true])] })) }];
    Plotly.react(el, tr, L, CFG);
  },
  s_ra(el) {
    const d = D.ra, col = [v("--s3"), v("--s2"), v("--s1")];
    const tr = Object.keys(d).map((k, i) => ({ type: "scatter", mode: "lines+markers", name: k, x: MESES, y: d[k], line: { color: col[i], width: 2 },
      marker: { size: 6, color: col[i] }, hovertemplate: `${k} · %{x}: %{y:.2f} mm/día<extra></extra>` }));
    Plotly.react(el, tr, lay({ showlegend: true, xaxis: ax(""), yaxis: ax("Ra* (mm/día)") }), CFG);
  },
  s_etpT(el) {
    const d = D.etpT;
    Plotly.react(el, [{ type: "scattergl", mode: "markers", x: d.T, y: d.ETP, customdata: d.Z,
      marker: { size: 4, color: d.Z, colorscale: "Earth", reversescale: true, opacity: .7,
        colorbar: { title: { text: "Z (m)", font: { size: 10 } }, thickness: 10, len: .8, tickfont: { size: 9 } } },
      hovertemplate: "Tmed %{x:.1f} °C · ETP %{y:,.0f} mm · Z %{customdata:,.0f} m<extra></extra>" }],
      lay({ xaxis: ax("Temperatura media (°C)"), yaxis: ax("ETP anual (mm/año)") }), CFG);
  },
  s_qa(el) {
    const d = D.qa, pal = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948", "#7f8c8d", "#0b6872"];
    const tr = Object.keys(d.q).map((n, i) => ({ type: "scatter", mode: "lines+markers", name: n, x: d.anos, y: d.q[n], connectgaps: false,
      line: { width: 1.5, color: pal[i % pal.length] }, marker: { size: 4 }, hovertemplate: `${n} %{x}: %{y:,.0f} m³/s<extra></extra>` }));
    Plotly.react(el, tr, lay({ showlegend: true, hovermode: "x unified", margin: { l: 56, r: 12, t: 50, b: 36 },
      legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { size: 10 } },
      xaxis: ax(""), yaxis: ax("Caudal medio anual (m³/s)", { rangemode: "tozero" }),
      shapes: [{ type: "rect", xref: "x", yref: "paper", x0: 1980.5, x1: 2010.5, y0: 0, y1: 1, fillcolor: v("--grid"), opacity: .45, line: { width: 0 }, layer: "below" }] }), CFG);
  },
  s_p12bar(el) {
    const d = D.p12bar;
    const tr = [["P", "P (lluvia)", "#86b6ef"], ["ETR", "ETR (Budyko)", "#1baf7a"], ["R", "Q estimado = P − ETR", "#0b6872"]].map(([k, n, c]) => ({
      type: "bar", name: n, x: d.prod, y: d[k], marker: { color: c }, hovertemplate: `${n} · %{x}: %{y:,.0f} mm/año<extra></extra>` }));
    Plotly.react(el, tr, lay({ showlegend: true, barmode: "group", bargap: .3, xaxis: ax(""),
      yaxis: ax("mm/año (escala logarítmica)", { type: "log", range: [Math.log10(500), Math.log10(8000)] }),
      shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: d.Robs, y1: d.Robs, line: { color: v("--ink"), width: 1.3, dash: "dot" } }],
      annotations: [{ xref: "paper", x: 1, y: Math.log10(d.Robs), xanchor: "right", yanchor: "bottom", showarrow: false,
        text: `Q observado ${d.Robs} mm/año`, font: { size: 10, color: v("--muted") } }] }), CFG);
  },
  s_bud(el) {
    const d = D.p12bud, col = { "IDEAM": "#52514e", "CHIRPS": "#2a78d6", "ERA5-Land": "#eb6834", "ERA5": "#1baf7a" };
    const f = Array.from({ length: 100 }, (_, i) => 0.05 + i * 0.02);
    const tr = [{ type: "scatter", mode: "lines", name: "Budyko (1974)", x: f, y: f.map(p => Math.sqrt(p * Math.tanh(1 / p) * (1 - Math.exp(-p)))),
      line: { color: v("--ink"), width: 1.6 }, hoverinfo: "skip" },
      { type: "scatter", mode: "lines", name: "Límites energía / agua", x: [0, 1, 2], y: [0, 1, 1], line: { color: v("--axis"), width: 1, dash: "dot" }, hoverinfo: "skip" }];
    Object.keys(d).forEach(p => tr.push({ type: "scatter", mode: "markers", name: p, x: d[p].phi, y: d[p].obs,
      customdata: d[p].est.map((e, i) => [e, d[p].k[i]]), marker: { size: 9, color: col[p], line: { color: v("--bg"), width: 1.5 } },
      hovertemplate: `<b>${p}</b> · %{customdata[0]}<br>φ = %{x:.2f} · ETR obs/P = %{y:.2f}<br>corrección de P necesaria: %{customdata[1]:+.0f} %<extra></extra>` }));
    Plotly.react(el, tr, lay({ showlegend: true, xaxis: ax("Índice de aridez φ = ETP / P", { range: [0, 1.2] }),
      yaxis: ax("ETR «observada» / P = 1 − Qobs / P", { range: [0, 1.05] }) }), CFG);
  },
  s_pp(el) {
    const d = D.pp, ks = ["CHIRPS", "IDEAM (kriging sin la estación)", "ERA5-Land", "ERA5"], ink = v("--ink");
    const tr = ks.map((k, i) => ({ type: "scatter", mode: "markers", name: k, x: d.obs, y: d[k], text: d.est, visible: i === 0,
      marker: { size: 6, color: v("--accent"), opacity: .7, line: { color: v("--bg"), width: 1 } },
      hovertemplate: `<b>%{text}</b><br>medida %{x:,.0f} mm · ${k} %{y:,.0f} mm<extra></extra>` }));
    tr.push({ type: "scatter", mode: "lines", x: [300, 30000], y: [300, 30000], line: { color: ink, width: 1 }, hoverinfo: "skip" });
    const L = lay({ xaxis: ax("P medida en la estación (mm/año)", { type: "log", range: [Math.log10(700), Math.log10(5000)] }),
      yaxis: ax("P del producto en la celda (mm/año)", { type: "log", range: [Math.log10(700), Math.log10(30000)] }),
      margin: { l: 60, r: 12, t: 46, b: 40 } });
    L.updatemenus = [{ type: "buttons", direction: "right", x: 0, xanchor: "left", y: 1.13, yanchor: "top", bgcolor: v("--bg"),
      bordercolor: v("--hair"), font: { size: 11, color: ink }, active: 0,
      buttons: ks.map((k, i) => ({ label: `${k.split(" (")[0]} · RMSE ${d.met[k][0].toLocaleString("es")} · r ${d.met[k][1]}`, method: "restyle",
        args: ["visible", ks.map((_, j) => j === i).concat([true])] })) }];
    Plotly.react(el, tr, L, CFG);
  },
