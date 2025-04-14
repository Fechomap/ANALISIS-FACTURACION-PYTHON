const { PythonShell } = require('python-shell');
const path = require('path');

async function ejecutarScript(script, args) {
    return new Promise((resolve, reject) => {
        const options = {
            mode: 'text',
            pythonPath: 'python3',
            pythonOptions: ['-u'],  // Unbuffered output para ver los logs en tiempo real
            scriptPath: path.join(__dirname, 'scripts'),
            args: args
        };

        const pyshell = new PythonShell(script, options);

        // Mostrar los logs en tiempo real
        pyshell.on('message', function(message) {
            console.log(message);
        });

        // Mostrar errores si ocurren
        pyshell.on('stderr', function(stderr) {
            console.log(stderr);
        });

        pyshell.end(function (err) {
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
        // 1. Ejecutar extract.py
        await ejecutarScript('extract.py', [
            'PDF-PEDIDOS',
            'output/data.xlsx',
            'output/log.txt'
        ]);

        // 2. Ejecutar detect.py
        await ejecutarScript('detect.py', [
            'PDF-FACTURAS',
            'output/data.xlsx',
            '--log_file',
            'output/log_facturas.txt'
        ]);

        // 3. Ejecutar detect2.py
        await ejecutarScript('detect2.py', [
            'PDF-FACTURAS',
            'output/data.xlsx',
            '--log_file',
            'output/log_facturas_nuevas.txt'
        ]);

    } catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}

main();