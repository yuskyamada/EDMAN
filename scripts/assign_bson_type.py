import sys
import signal
import argparse
from pathlib import Path
from edman import DB, JsonManager
from action import Action

# Ctrl-Cを押下された時の対策
signal.signal(signal.SIGINT, lambda sig, frame: sys.exit('\n'))

# コマンドライン引数処理
parser = argparse.ArgumentParser(description='DB内のRefドキュメントに型を適応するスクリプト')
parser.add_argument('path', help='JSON file path.')
parser.add_argument('-l', '--logfile',
                    help='Output logfile path. defalut is current dir.')
parser.add_argument('-n', '--no_logfile', help='Do not output log file.',
                    action='store_true')
parser.add_argument('-i', '--inifile', help='DB connect file path.')
args = parser.parse_args()

# 結果を記録する場合はパスの存在を調べる

log_p = Path(args.logfile) if args.logfile is not None else Path.cwd()
if not log_p.exists() or not log_p.is_dir():
    sys.exit('指定のログファイル用ディレクトリパスが不正です')

# JSONのパスを取得
p = Path(args.path)
if not p.exists() or not p.is_file() or p.suffix != '.json':
    sys.exit('指定のJSONファイルがありません')

# 接続用iniファイル読み込み
con = Action.reading_config_file(args.inifile)

db = DB(con)
process_data = {}

# ファイル読み込み、実行
# ファイル単体の場合でもジェネレータなのでループを使用する
for i in Action.file_gen((p,)):
    process_data = db.bson_type(i)

# ログファイル書き出し処理
if not args.no_logfile:
    jm = JsonManager()
    jm.save(process_data, log_p, name='type_assigned_log', date=True)
