
let currentExtractedRows = [];
let isSaving = false;
let currentLedgerBatchId = null;

const API_BASE = "http://localhost:8000";

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

async function uploadLedger() {
    const fileInput = document.getElementById("ledgerInput");
    const resultsDiv = document.getElementById("results");

    if (!fileInput.files.length) {
        alert("Please select or snap a ledger photo first.");
        return;
    }

    const file = fileInput.files[0];

    if (!file.type.startsWith("image/")) {
        alert("Please select a valid image file.");
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        alert("The image must be 10 MB or smaller.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    resultsDiv.innerHTML = `
        <p class="text-center text-emerald-600 font-medium py-4">
            Processing ledger with Muse Spark. Please wait...
        </p>`;

    try {
        const response = await fetch(`${API_BASE}/api/extract`, {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Ledger extraction failed.");
        }

        const extracted = Array.isArray(data) ? data : data.rows;
        if (!Array.isArray(extracted)) {
            throw new Error("The API returned an unexpected response.");
        }

        currentLedgerBatchId = data.ledger_batch_id || crypto.randomUUID();

        currentExtractedRows = extracted.map(row => ({
            date: row.date ?? "",
            description: row.description ?? "",
            type: row.type === "expense" ? "expense" : "income",
            amount: row.amount ?? "",
            credit_customer: row.credit_customer ?? ""
        }));

        renderRows(currentExtractedRows);

    } catch (error) {
        resultsDiv.innerHTML = `
            <p class="text-red-600 text-center py-4">
                ${escapeHTML(error.message)}
            </p>`;
        console.error("Extraction error:", error);
    }
}

function renderRows(rows) {
    const resultsDiv = document.getElementById("results");

    if (!rows.length) {
        resultsDiv.innerHTML = `
            <p class="text-amber-700 text-center py-4">
                No transactions were detected. Try a clearer photo.
            </p>`;
        return;
    }

    let html = `
        <p class="text-sm text-slate-600 mb-3">
            Review every transaction and correct any AI mistakes before saving.
        </p>
        <div class="space-y-4">`;

    rows.forEach((row, index) => {
        const date = escapeHTML(row.date);
        const description = escapeHTML(row.description);
        const amount = escapeHTML(row.amount);
        const customer = escapeHTML(row.credit_customer);

        html += `
            <div class="ledger-row-card p-4 bg-slate-50 rounded-xl
                        border border-slate-200 space-y-3">

                <div>
                    <label for="date-${index}"
                           class="block text-xs font-medium text-slate-500 mb-1">
                        Transaction date
                    </label>
                    <input
                        type="text"
                        id="date-${index}"
                        value="${date}"
                        placeholder="e.g. 21/10/2026"
                        required
                        class="w-full p-2 rounded-lg border border-slate-300
                               bg-white focus:outline-none focus:border-emerald-500"
                    />
                </div>

                <div>
                    <label for="desc-${index}"
                           class="block text-xs font-medium text-slate-500 mb-1">
                        Description
                    </label>
                    <input
                        type="text"
                        id="desc-${index}"
                        value="${description}"
                        placeholder="Transaction description"
                        required
                        class="w-full p-2 rounded-lg border border-slate-300
                               bg-white focus:outline-none focus:border-emerald-500"
                    />
                </div>

                <div>
                    <label for="type-${index}"
                           class="block text-xs font-medium text-slate-500 mb-1">
                        Transaction type
                    </label>
                    <select
                        id="type-${index}"
                        class="w-full p-2 rounded-lg border border-slate-300
                               bg-white focus:outline-none focus:border-emerald-500">
                        <option value="income"
                            ${row.type === "income" ? "selected" : ""}>
                            Income / Sale
                        </option>
                        <option value="expense"
                            ${row.type === "expense" ? "selected" : ""}>
                            Expense / Purchase
                        </option>
                    </select>
                </div>

                <div>
                    <label for="amount-${index}"
                           class="block text-xs font-medium text-slate-500 mb-1">
                        Amount (ZAR)
                    </label>
                    <input
                        type="number"
                        id="amount-${index}"
                        value="${amount}"
                        min="0.01"
                        step="0.01"
                        required
                        class="w-full p-2 rounded-lg border border-slate-300
                               bg-white font-semibold focus:outline-none
                               focus:border-emerald-500"
                    />
                </div>

                <div>
                    <label for="customer-${index}"
                           class="block text-xs font-medium text-slate-500 mb-1">
                        Customer owing money (optional)
                    </label>
                    <input
                        type="text"
                        id="customer-${index}"
                        value="${customer}"
                        placeholder="Customer name, if sold on credit"
                        class="w-full p-2 rounded-lg border border-slate-300
                               bg-white focus:outline-none focus:border-emerald-500"
                    />
                </div>
            </div>`;
    });

    html += `
        <button
            id="saveRowsBtn"
            onclick="confirmAndStore()"
            class="w-full bg-emerald-600 hover:bg-emerald-700
                   text-white font-semibold py-3 rounded-xl transition">
            Confirm and Store Transactions
        </button>

        <p class="text-xs text-slate-500 text-center">
            Check all dates, descriptions, types and amounts before saving.
        </p>
        </div>`;

    resultsDiv.innerHTML = html;
}

async function confirmAndStore() {
    if (isSaving) return;

    if (!currentExtractedRows.length) {
        alert("Please extract a ledger before saving.");
        return;
    }

    const updatedRows = [];

    for (let index = 0; index < currentExtractedRows.length; index++) {
        const date = document.getElementById(`date-${index}`).value.trim();
        const description = document.getElementById(`desc-${index}`).value.trim();
        const type = document.getElementById(`type-${index}`).value;
        const amountInput = document.getElementById(`amount-${index}`);
        const amount = Number(amountInput.value);
        const customer = document.getElementById(`customer-${index}`).value.trim();

        if (!date || !description) {
            alert(`Transaction ${index + 1}: date and description are required.`);
            return;
        }

        if (!["income", "expense"].includes(type)) {
            alert(`Transaction ${index + 1}: select a valid transaction type.`);
            return;
        }

        if (!amountInput.value || !Number.isFinite(amount) || amount <= 0) {
            alert(`Transaction ${index + 1}: enter an amount greater than zero.`);
            amountInput.focus();
            return;
        }

        updatedRows.push({
            date,
            description,
            type,
            amount,
            credit_customer: customer || null
        });
    }

    const saveButton = document.getElementById("saveRowsBtn");
    isSaving = true;

    if (saveButton) {
        saveButton.disabled = true;
        saveButton.textContent = "Saving transactions...";
        saveButton.classList.add("opacity-60", "cursor-not-allowed");
    }

    try {
         
        const response = await fetch(`${API_BASE}/api/store`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ledger_batch_id: currentLedgerBatchId,
                rows: updatedRows
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                typeof result.detail === "string"
                    ? result.detail
                    : JSON.stringify(result.detail || "Database save failed.")
            );
        }

        alert(`Success! ${result.inserted_count} transactions saved to Supabase.`);

        currentExtractedRows = [];
        currentLedgerBatchId = null;
        document.getElementById("results").innerHTML = `
            <p class="text-emerald-700 text-center py-4">
                Transactions saved successfully. Upload another ledger when ready.
            </p>`;

    } catch (error) {
        alert(`Could not save transactions: ${error.message}`);
        console.error("Storage error:", error);

        if (saveButton) {
            saveButton.disabled = false;
            saveButton.textContent = "Retry Saving Transactions";
            saveButton.classList.remove("opacity-60", "cursor-not-allowed");
        }
    } finally {
        isSaving = false;
    }
}
