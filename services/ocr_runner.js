const path = require('path');
const fs = require('fs');
const { createWorker } = require('tesseract.js');

const imgPath = process.argv[2];
const lang = process.argv[3] || 'mal+eng+hin+tam';

if (!imgPath || !fs.existsSync(imgPath)) {
    console.error("Error: Image path not provided or does not exist.");
    process.exit(1);
}

const tessdataDir = path.resolve(__dirname, '../models/tessdata');

(async () => {
    try {
        const worker = await createWorker(lang, 1, {
            cachePath: tessdataDir,
            gzip: false,
            errorHandler: (err) => { /* suppress verbose progress logs */ },
        });
        const ret = await worker.recognize(imgPath);
        const text = (ret && ret.data && ret.data.text) ? ret.data.text.trim() : '';
        process.stdout.write(text);
        await worker.terminate();
        process.exit(0);
    } catch (e) {
        console.error("OCR execution error:", e.message || e);
        process.exit(2);
    }
})();
