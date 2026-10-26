let currentExtractedRows = [];

async function uploadLedger() {
    const fileInput = document.getElementById('ledgerInput');
    const resultsDiv = document.getElementById('results');

    if (fileInput.files.length === 0) {
        alert("Please select or snap a photo first!");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    resultsDiv.innerHTML = `<p class="text-center text-emerald-600 font-medium py-4">Processing ledger with Llama Vision...</p>`;

    try {
        const response = await fetch('http://localhost:8000/api/extract', {
            method: 'POST',
            body: formData
        });

        currentExtractedRows = await response.json();
        renderRows(currentExtractedRows);
    } catch (err) {
        resultsDiv.innerHTML = `<p class="text-red-500 text-center py-4">Error connecting to backend API.</p>`;
        console.error(err);
    }
}

function renderRows(rows) {
    const resultsDiv = document.getElementById('results');
    let html = '<div class="space-y-3">';
    
    rows.forEach((row, index) => {
        html += `
            <div class="ledger-row-card p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <div class="flex justify-between items-center text-xs text-slate-500">
                    <input type="text" id="date-${index}" value="${row.date}" class="bg-transparent font-medium text-slate-500 border-b border-transparent focus:border-emerald-500 focus:outline-none" />
                    <span class="px-2 py-0.5 rounded-full font-medium ${row.type === 'income' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}">${row.type}</span>
                </div>
                <input type="text" id="desc-${index}" value="${row.description}" class="w-full font-medium bg-transparent border-b border-slate-200 text-slate-800 pb-0.5 focus:outline-none focus:border-emerald-500" />
                <div class="flex justify-between items-center pt-1">
                    <span class="text-xs text-slate-400">Rands (ZAR):</span>
                    <input type="number" id="amount-${index}" value="${row.amount}" class="w-24 text-right font-bold bg-transparent border-b border-slate-200 text-slate-800 pb-0.5 focus:outline-none focus:border-emerald-500" />
                </div>
            </div>
        `;
    });
    
    html += `
        <button onclick="confirmAndStore()" class="w-full bg-slate-800 hover:bg-slate-900 text-white font-medium py-2.5 rounded-xl transition shadow-sm mt-4">
            Confirm and Store to Ledger ✅
        </button>
    </div>`;
    
    resultsDiv.innerHTML = html;
}

async function confirmAndStore() {
    const updatedRows = currentExtractedRows.map((row, index) => ({
        date: document.getElementById(`date-${index}`).value,
        description: document.getElementById(`desc-${index}`).value,
        type: row.type,
        amount: parseFloat(document.getElementById(`amount-${index}`).value),
        credit_customer: row.credit_customer
    }));

    try {
        const response = await fetch('http://localhost:8000/api/store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedRows)
        });

        const resData = await response.json();
        if (response.ok) {
            alert(`Success! ${resData.inserted_count} transactions stored directly to Supabase! 🚀`);
        } else {
            alert("Error saving to database: " + JSON.stringify(resData.detail));
        }
    } catch (err) {
        console.error(err);
        alert("Failed to connect to backend server on port 8000.");
    }
}
