import sys
import signal
import configparser
import argparse
from pathlib import Path
from edman import DB, File
from action import Action

# Ctrl-Cを押下された時の対策
signal.signal(signal.SIGINT, lambda sig, frame: sys.exit('\n'))

# コマンドライン引数処理
parser = argparse.ArgumentParser(
    description='ファイルを実験データから削除するスクリプト')
# parser.add_argument('-c', '--collection', help='collection name.')
parser.add_argument('objectid', help='objectid str.')
# クエリは structureがembの時だけ
parser.add_argument('-q', '--query', default=None,
                    help='Ref is ObjectId or Emb is query list strings.')
args = parser.parse_args()

# iniファイル読み込み
settings = configparser.ConfigParser()
settings.read(Path.cwd() / 'ini' / 'db.ini')
con = dict([i for i in settings['DB'].items()])

db = DB(con)
file = File(db.get_db)

# 対象oidの所属コレクションを自動的に取得 ※動作が遅い場合は使用しないこと
collection = db.find_collection_from_objectid(args.objectid)

# ドキュメント構造の取得
structure = db.get_structure(collection, args.objectid)

# クエリの変換
query = Action.file_query_eval(args.query, structure)

# ファイル名一覧を取得
file_names = file.get_file_names(collection, args.objectid, structure, query)
file_oids = []
# ファイル名一覧を画面表示&file_oid用リスト作成
for idx, (oid, filename) in enumerate(file_names.items()):
    print('(' + str(idx) + ')', filename, oid)
    file_oids.append(oid)

# 表示されている選択番号を入力
if len(file_names) > 0:
    while True:
        selected_idx = input('0 - ' + str(len(file_names) - 1) + ' > ')
        if selected_idx.isdecimal() and (
                0 <= int(selected_idx) < len(file_names)):
            break
        else:
            print('Required!')
else:
    sys.exit('インデックスが不正です')

# 該当するファイルを削除
if file.delete(file_oids[int(selected_idx)], collection, args.objectid,
               structure, query):
    print('削除完了')
else:
    print('削除失敗')