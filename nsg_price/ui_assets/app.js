const state = { config: null, games: [], selected: null, matches: [], draggedSlug: null };
    const merchantNames = {};
    const $ = (id) => document.getElementById(id);

    function text(value) {
      return value == null ? "" : String(value);
    }

    function html(value) {
      return text(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function setStatus(id, tone, message) {
      const el = $(id);
      el.className = `status ${tone || "soft"}`;
      el.textContent = message;
    }

    function gameCoverage(game) {
      const merchants = Object.entries(state.config?.merchants || {})
        .filter(([, merchant]) => merchant.enabled !== false)
        .map(([key]) => key);
      const merchantIds = game?.merchant_ids || {};
      const filled = merchants.filter((key) => text(merchantIds[key]?.game_id).trim()).length;
      return { filled, total: merchants.length };
    }

    function selectedMatchSummary() {
      const total = state.matches.length;
      const matched = state.matches.filter((item) => item.status === "matched").length;
      return total ? `${matched}/${total} 项可直接应用` : "未执行匹配";
    }

    function matchDisplay(item) {
      if (item.search_status === "failed" && (item.raw_count || 0) > 0) {
        if (item.status === "matched") return { tone: "ok", label: "部分结果可应用", action: "接口中断，但候选可写入" };
        return { tone: "info", label: "部分结果", action: "接口中断，先复核已搜到候选" };
      }
      if (item.search_status === "failed") return { tone: "bad", label: "请求失败", action: "检查网络或商家接口" };
      if (item.status === "matched") return { tone: "ok", label: "可直接应用", action: "可一键写入" };
      if ((item.raw_count || 0) === 0) return { tone: "soft", label: "无候选", action: "换关键词或人工查询" };
      return { tone: "info", label: "需要复核", action: "人工确认后再写入" };
    }

    function matchSubtext(item) {
      const countText = item.raw_count ? `候选 ${item.raw_count} 条` : "没有可用候选";
      if (item.search_status === "failed" && item.search_error) {
        return `${countText} · 部分请求失败：${text(item.search_error)}`;
      }
      return countText;
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "content-type": "application/json" },
        ...options,
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        throw new Error(data.error || response.statusText);
      }
      return data;
    }

    async function load() {
      const data = await api("/api/config");
      state.config = data;
      state.games = data.games || [];
      Object.keys(merchantNames).forEach((key) => delete merchantNames[key]);
      Object.entries(data.merchants || {}).forEach(([key, merchant]) => merchantNames[key] = merchant.name || key);
      if (!state.selected && state.games.length) state.selected = state.games[0].slug;
      if (state.selected && !state.games.find((game) => game.slug === state.selected)) {
        state.selected = state.games[0]?.slug || null;
      }
      render();
    }

    function selectedGame() {
      return state.games.find((game) => game.slug === state.selected) || null;
    }

    function clearDropMarkers() {
      $("games").querySelectorAll(".drop-target, .drop-after").forEach((row) => {
        row.classList.remove("drop-target", "drop-after");
      });
    }

    function autoScrollGames(clientY) {
      const list = $("games");
      const rect = list.getBoundingClientRect();
      const scrollMargin = 76;
      let delta = 0;
      if (clientY < rect.top + scrollMargin) {
        delta = -Math.ceil((scrollMargin - (clientY - rect.top)) / 4);
      } else if (clientY > rect.bottom - scrollMargin) {
        delta = Math.ceil((scrollMargin - (rect.bottom - clientY)) / 4);
      }
      if (delta) list.scrollTop += delta;
      list.classList.toggle("auto-scroll-up", delta < 0);
      list.classList.toggle("auto-scroll-down", delta > 0);
    }

    function stopAutoScrollGames() {
      $("games").classList.remove("auto-scroll-up", "auto-scroll-down");
    }

    function render() {
      const filter = $("filter").value.trim().toLowerCase();
      const enabledCount = state.games.filter((game) => game.enabled !== false).length;
      $("summary").textContent = `${enabledCount}/${state.games.length} 款启用`;
      $("matchSummary").textContent = selectedMatchSummary();
      $("games").innerHTML = "";
      const filteredGames = state.games
        .filter((game) => !filter || `${game.slug} ${game.name} ${game.platform}`.toLowerCase().includes(filter));
      filteredGames
        .forEach((game) => {
          const coverage = gameCoverage(game);
          const row = document.createElement("div");
          row.className = "game-row";
          row.draggable = true;
          row.dataset.slug = game.slug;
          const button = document.createElement("button");
          button.className = `game-item ${game.slug === state.selected ? "active" : ""}`;
          button.innerHTML = `
            <span class="drag-handle" aria-hidden="true">::</span>
            <span class="game-title">${html(game.name)}</span>
            <span class="pill ${game.enabled === false ? "bad" : "ok"}">${game.enabled === false ? "停用" : "启用"}</span>
            <span class="game-sub">${html(game.slug)} · ${html(game.platform)}</span>
            <span class="game-meta">
              <span class="pill ${coverage.filled === coverage.total ? "ok" : coverage.filled ? "info" : "bad"}">ID ${coverage.filled}/${coverage.total}</span>
            </span>
          `;
          button.onclick = () => {
            state.selected = game.slug;
            state.matches = [];
            setStatus("searchStatus", "soft", "还没有执行匹配");
            render();
          };
          row.addEventListener("dragstart", (event) => {
            state.draggedSlug = game.slug;
            row.classList.add("dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", game.slug);
          });
          row.addEventListener("dragend", () => {
            state.draggedSlug = null;
            row.classList.remove("dragging");
            clearDropMarkers();
            stopAutoScrollGames();
          });
          row.addEventListener("dragover", (event) => {
            const draggedSlug = state.draggedSlug || event.dataTransfer.getData("text/plain");
            if (!draggedSlug || draggedSlug === game.slug) return;
            event.preventDefault();
            autoScrollGames(event.clientY);
            const rect = row.getBoundingClientRect();
            const placeAfter = event.clientY > rect.top + rect.height / 2;
            clearDropMarkers();
            row.classList.add("drop-target");
            row.classList.toggle("drop-after", placeAfter);
          });
          row.addEventListener("dragleave", () => row.classList.remove("drop-target", "drop-after"));
          row.addEventListener("drop", (event) => {
            event.preventDefault();
            const sourceSlug = state.draggedSlug || event.dataTransfer.getData("text/plain");
            if (!sourceSlug || sourceSlug === game.slug) return;
            const rect = row.getBoundingClientRect();
            const placement = event.clientY > rect.top + rect.height / 2 ? "after" : "before";
            reorderGame(sourceSlug, game.slug, placement);
          });
          row.appendChild(button);
          $("games").appendChild(row);
        });
      $("games").ondragover = (event) => {
        if (!state.draggedSlug) return;
        event.preventDefault();
        autoScrollGames(event.clientY);
      };
      $("games").ondragleave = stopAutoScrollGames;
      renderForm();
      renderManualPriceForm();
      renderMerchantSettings();
      renderMatches();
    }

    function renderMerchantSettings() {
      const container = $("merchantSettings");
      container.innerHTML = "";
      Object.entries(state.config?.merchants || {}).forEach(([key, merchant]) => {
        const enabled = merchant.enabled !== false;
        const box = document.createElement("div");
        box.className = "merchant";
        box.innerHTML = `
          <div class="merchant-head">
            <h3>${html(merchant.name || key)}</h3>
            <span class="pill ${enabled ? "ok" : "bad"}">${enabled ? "启用" : "停用"}</span>
          </div>
          <label>采集状态
            <select data-merchant-toggle="${html(key)}">
              <option value="true" ${enabled ? "selected" : ""}>启用</option>
              <option value="false" ${enabled ? "" : "selected"}>停用</option>
            </select>
          </label>
          <div class="hint">${enabled ? "会参与采集、匹配和覆盖率统计。" : "已跳过采集，适合接口暂时不可用时关闭。"}</div>
        `;
        box.querySelector("select").onchange = (event) => updateMerchantEnabled(key, event.target.value === "true");
        container.appendChild(box);
      });
    }

    async function updateMerchantEnabled(key, enabled) {
      setStatus("merchantStatus", "info", "正在保存回收商状态...");
      try {
        await api(`/api/merchants/${encodeURIComponent(key)}`, {
          method: "POST",
          body: JSON.stringify({ enabled }),
        });
        setStatus("merchantStatus", "ok", "回收商状态已保存。");
        await load();
      } catch (error) {
        setStatus("merchantStatus", "warn", error.message);
      }
    }

    function renderForm() {
      const game = selectedGame();
      $("deleteBtn").disabled = !game;
      $("saveBtn").disabled = false;
      $("slug").value = text(game?.slug);
      $("name").value = text(game?.name);
      $("searchKeyword").value = text(game?.search_keyword);
      $("platform").value = text(game?.platform || "Nintendo Switch");
      $("enabled").value = String(game?.enabled !== false);
      $("currentName").textContent = text(game?.name || "请选择左侧游戏");
      $("currentEnabled").className = `pill ${game ? (game.enabled === false ? "bad" : "ok") : "soft"}`;
      $("currentEnabled").textContent = !game ? "未选择" : game.enabled === false ? "当前停用" : "当前启用";
      const coverage = gameCoverage(game);
      $("coverageSummary").textContent = game ? `商家 ID ${coverage.filled}/${coverage.total}` : "商家 ID 0/0";
      $("currentMeta").textContent = game
        ? `${text(game.platform)} · ${text(game.slug)} · 已配置 ${coverage.filled}/${coverage.total} 个商家商品 ID`
        : "选择一款游戏后，这里会显示平台、Slug 和商家 ID 完整度。";
      $("merchants").innerHTML = "";
      const merchantIds = game?.merchant_ids || {};
      if (!game) {
        $("merchants").innerHTML = `<div class="empty">请先从左侧选择一款游戏，或点击上方“新增游戏”开始创建。</div>`;
        return;
      }
      Object.entries(merchantNames).forEach(([key, name]) => {
        const ids = merchantIds[key] || {};
        const hasId = text(ids.game_id).trim();
        const box = document.createElement("div");
        box.className = "merchant";
        box.innerHTML = `
          <div class="merchant-head">
            <h3>${html(name)}</h3>
            <span class="pill ${hasId ? "ok" : "bad"}">${hasId ? "已填写" : "待补充"}</span>
          </div>
          <label>商品 ID
            <input data-merchant="${html(key)}" data-field="game_id" value="${html(ids.game_id)}">
          </label>
          <div class="hint">${hasId ? "已具备采集条件，可直接参与价格抓取。" : "建议先执行自动匹配，或手动补充后再采集。"}</div>
        `;
        $("merchants").appendChild(box);
      });
    }

    function renderManualPriceForm() {
      const game = selectedGame();
      const merchantSelect = $("manualMerchant");
      const previousMerchant = merchantSelect.value;
      merchantSelect.innerHTML = "";
      Object.entries(merchantNames).forEach(([key, name]) => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = name;
        merchantSelect.appendChild(option);
      });
      if (previousMerchant && merchantNames[previousMerchant]) {
        merchantSelect.value = previousMerchant;
      }
      $("manualPriceBtn").disabled = !game || !merchantSelect.value;
      if (!game) {
        $("manualRecyclePrice").value = "";
      }
    }

    function collectForm() {
      const merchant_ids = {};
      $("merchants").querySelectorAll("input[data-merchant]").forEach((input) => {
        const key = input.dataset.merchant;
        const field = input.dataset.field;
        merchant_ids[key] ||= {};
        merchant_ids[key][field] = input.value.trim();
      });
      return {
        original_slug: state.selected,
        slug: $("slug").value.trim(),
        name: $("name").value.trim(),
        search_keyword: $("searchKeyword").value.trim(),
        platform: $("platform").value,
        enabled: $("enabled").value === "true",
        merchant_ids,
      };
    }

    async function saveGame() {
      setStatus("formStatus", "info", "正在保存当前游戏...");
      try {
        const payload = collectForm();
        const data = await api("/api/games", { method: "POST", body: JSON.stringify(payload) });
        state.selected = data.slug;
        setStatus("formStatus", "ok", "已保存，列表与商家 ID 已刷新。");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function deleteGame() {
      const game = selectedGame();
      if (!game) return;
      setStatus("formStatus", "warn", "正在删除当前游戏...");
      try {
        await api(`/api/games/${encodeURIComponent(game.slug)}`, { method: "DELETE" });
        state.selected = null;
        setStatus("formStatus", "ok", "已删除，已切回列表首项。");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function saveManualPrice() {
      const game = selectedGame();
      if (!game) return;
      const recyclePrice = $("manualRecyclePrice").value.trim();
      if (!recyclePrice) {
        setStatus("manualPriceStatus", "warn", "请填写回收价。");
        return;
      }
      setStatus("manualPriceStatus", "info", "正在保存手动价格...");
      try {
        await api("/api/prices/manual", {
          method: "POST",
          body: JSON.stringify({
            game_slug: game.slug,
            merchant: $("manualMerchant").value,
            recycle_price: recyclePrice,
          }),
        });
        setStatus("manualPriceStatus", "ok", "手动价格已写入今天的价格记录。");
      } catch (error) {
        setStatus("manualPriceStatus", "warn", error.message);
      }
    }

    async function moveGame(slug, direction) {
      if (!slug || !direction) return;
      setStatus("formStatus", "info", direction === "up" ? "Moving game up..." : "Moving game down...");
      try {
        const data = await api("/api/games/reorder", {
          method: "POST",
          body: JSON.stringify({ slug, direction }),
        });
        state.selected = data.slug || slug;
        setStatus("formStatus", "ok", "Game order saved.");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function reorderGame(slug, targetSlug, placement) {
      if (!slug || !targetSlug || slug === targetSlug) return;
      setStatus("formStatus", "info", "正在保存拖拽排序...");
      try {
        const data = await api("/api/games/reorder", {
          method: "POST",
          body: JSON.stringify({ slug, target_slug: targetSlug, placement }),
        });
        state.selected = data.slug || slug;
        setStatus("formStatus", "ok", "排序已保存。");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function searchGame(apply = false) {
      const game = selectedGame();
      if (!game) return;
      setStatus("searchStatus", "info", apply ? "正在搜索并写入高置信候选..." : "正在搜索当前游戏的可用候选...");
      try {
        const keyword = $("searchKeyword").value.trim();
        const params = new URLSearchParams({ game: game.slug, apply: apply ? "1" : "0" });
        if (keyword) params.set("keyword", keyword);
        const data = await api(`/api/search?${params.toString()}`);
        state.matches = data.matches || [];
        const matched = state.matches.filter((item) => item.status === "matched").length;
        setStatus("searchStatus", apply ? "ok" : matched ? "ok" : "soft", apply ? `已写入 ${data.updated} 项高置信候选。` : `已完成搜索，找到 ${matched} 项可直接应用结果。`);
        if (apply) await load();
        renderMatches();
      } catch (error) {
        setStatus("searchStatus", "warn", error.message);
      }
    }

    function renderMatches() {
      $("matches").innerHTML = "";
      if (!state.matches.length) {
        $("matches").innerHTML = `<tr><td colspan="6"><div class="empty">还没有匹配结果。点击“自动匹配当前游戏”后，这里会展示候选和建议动作。</div></td></tr>`;
        $("matchSummary").textContent = "未执行匹配";
        return;
      }
      $("matchSummary").textContent = selectedMatchSummary();
      state.matches.forEach((item, index) => {
        const best = item.best || {};
        const candidates = item.candidates || [];
        const candidateOptions = candidates.map((candidate, candidateIndex) => {
          const label = `${text(candidate.matched_name)} · ID ${text(candidate.game_id)} · ${text(candidate.confidence)}`;
          return `<option value="${candidateIndex}" ${candidateIndex === 0 ? "selected" : ""}>${html(label)}</option>`;
        }).join("");
        const display = matchDisplay(item);
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${html(merchantNames[item.merchant] || item.merchant)}</td>
          <td class="text-center"><span class="pill ${display.tone}">${html(display.label)}</span></td>
          <td>
            <button type="button" data-apply-candidate="${index}" ${candidates.length ? "" : "disabled"}>写入此项</button>
          </td>
          <td>
            ${candidates.length ? `<select data-candidate-select="${index}">${candidateOptions}</select>` : `<div class="match-name">${html(item.search_error || "-")}</div>`}
            <div class="match-sub">${html(matchSubtext(item))}</div>
          </td>
          <td class="text-right">${html(best.game_id || "-")}</td>
          <td class="text-right">${html(best.confidence || "-")}</td>
        `;
        $("matches").appendChild(tr);
      });
      $("matches").querySelectorAll("button[data-apply-candidate]").forEach((button) => {
        button.onclick = () => applyCandidate(Number(button.dataset.applyCandidate));
      });
    }

    async function applyCandidate(index) {
      const item = state.matches[index];
      const select = $("matches").querySelector(`select[data-candidate-select="${index}"]`);
      const candidate = item?.candidates?.[Number(select?.value || 0)];
      if (!item || !candidate) return;
      setStatus("searchStatus", "info", `正在写入 ${merchantNames[item.merchant] || item.merchant} 的候选 ID...`);
      try {
        await api("/api/search/apply", {
          method: "POST",
          body: JSON.stringify({
            game_slug: item.game_slug,
            merchant: item.merchant,
            game_id: candidate.game_id,
            uuid: candidate.uuid || "",
          }),
        });
        setStatus("searchStatus", "ok", "候选 ID 已写入。");
        await load();
      } catch (error) {
        setStatus("searchStatus", "warn", error.message);
      }
    }

    $("reloadBtn").onclick = load;
    $("newBtn").onclick = () => {
      state.selected = null;
      state.matches = [];
      $("slug").value = "";
      $("name").value = "";
      $("searchKeyword").value = "";
      $("platform").value = "Nintendo Switch";
      $("enabled").value = "true";
      renderForm();
      renderManualPriceForm();
      setStatus("formStatus", "soft", "正在创建新游戏，填写后点击“保存当前游戏”。");
      setStatus("searchStatus", "soft", "新游戏保存后才可执行自动匹配。");
    };
    $("filter").oninput = render;
    $("saveBtn").onclick = saveGame;
    $("deleteBtn").onclick = deleteGame;
    $("manualPriceBtn").onclick = saveManualPrice;
    $("searchBtn").onclick = () => searchGame(false);
    $("applySearchBtn").onclick = () => searchGame(true);
    load().catch((error) => setStatus("formStatus", "warn", error.message));
