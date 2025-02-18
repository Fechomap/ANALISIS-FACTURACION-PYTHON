const { PythonShell } = require('python-shell');
const path = require('path');

async function ejecutarScript(script, args) {
    return new Promise((resolve, reject) => {
        PythonShell.run(path.join(__dirname, 'scripts', script), {
            args: args,
            pythonPath: 'python3'
        }, (err) => {
            if (err) {
                reject(err);
                return;
            }
            resolve();
        });
    });
}

async function main() {
    try {
        // Ejecutar procesamiento de pedidos
        await ejecutarScript('extract.py', [
            'PDF-PEDIDOS',
            'output/data.xlsx',
            'output/log.txt'
        ]);

        // Ejecutar procesamiento de facturas
        await ejecutarScript('detect.py', [
            'PDF-FACTURAS',
            'output/data.xlsx',
            '--log_file',
            'output/log_facturas.txt'
        ]);

    } catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}

main();