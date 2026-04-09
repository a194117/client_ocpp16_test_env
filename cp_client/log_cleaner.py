import os
import zipfile
from datetime import datetime
from glob import glob
from collections import defaultdict

def archive_old_logs(log_dir, archive_subdir="archived", processed_subdir=None):
    """
    Compacta todos os logs de dias anteriores (qualquer data < hoje) em arquivos .zip,
    agrupando por data de modificação.

    Args:
        log_dir: Diretório onde os logs estão (ex.: 'logs/').
        archive_subdir: Subdiretório dentro de log_dir onde os .zip serão salvos.
        processed_subdir: Subdiretório para onde os arquivos originais serão movidos após o zip.
                          Se None, os arquivos serão excluídos.
    """
    # Cria diretórios necessários
    archive_dir = os.path.join(log_dir, archive_subdir)
    processed_dir = os.path.join(log_dir, processed_subdir) if processed_subdir else None
    os.makedirs(archive_dir, exist_ok=True)
    if processed_dir:
        os.makedirs(processed_dir, exist_ok=True)

    # Dicionário para agrupar arquivos por data (YYYY-MM-DD)
    files_by_date = defaultdict(list)

    # Varre todos os arquivos dentro de log_dir (não recursivo)
    for filepath in glob(os.path.join(log_dir, "*")):
        if not os.path.isfile(filepath):
            continue
        # Ignora diretórios internos (archived, processed) se existirem
        if os.path.basename(filepath) in (archive_subdir, processed_subdir):
            continue

        # Obtém a data de modificação do arquivo (apenas a parte da data)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).date()
        hoje = datetime.now().date()

        # Se o arquivo foi modificado hoje, NÃO arquiva (ainda está em uso)
        if mtime == hoje:
            continue

        # Agrupa por data (ex.: '2025-04-08')
        files_by_date[mtime.isoformat()].append(filepath)

    if not files_by_date:
        print("Nenhum arquivo de log de dias anteriores encontrado.")
        return

    # Para cada data, cria um zip contendo todos os arquivos daquela data
    for date_str, file_list in files_by_date.items():
        zip_name = f"logs_{date_str}.zip"
        zip_path = os.path.join(archive_dir, zip_name)

        # Se o zip já existir, pula (evita duplicação)
        if os.path.exists(zip_path):
            continue
        
        print(f"Criando {zip_path} com {len(file_list)} arquivo(s)...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in file_list:
                arcname = os.path.basename(f)   # apenas o nome do arquivo, sem path
                zipf.write(f, arcname)

        # Após criar o zip com sucesso, remove ou move os arquivos originais
        if processed_dir:
            # Move para a subpasta 'processed' (seguro, não perde os dados)
            for f in file_list:
                dest = os.path.join(processed_dir, os.path.basename(f))
                os.rename(f, dest)
                print(f"  Movido: {f} -> {dest}")
        else:
            # Remove os arquivos originais (cuidado!)
            for f in file_list:
                os.remove(f)

    print("Limpeza de logs concluída.")