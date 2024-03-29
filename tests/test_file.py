import configparser
import tempfile
import gzip
from unittest import TestCase
from pathlib import Path
import gridfs
from pymongo import errors, MongoClient
from bson import ObjectId, DBRef
from edman import Config, Convert, DB, File
from edman.exceptions import EdmanDbProcessError


class TestFile(TestCase):

    db = None
    db_server_connect = False
    test_ini = []
    client = None

    @classmethod
    def setUpClass(cls):

        # 設定読み込み
        settings = configparser.ConfigParser()
        settings.read(Path.cwd() / 'ini' / 'test_db.ini')
        cls.test_ini = dict(settings.items('DB'))
        cls.test_ini['port'] = int(cls.test_ini['port'])

        # DB作成のため、pymongoから接続
        cls.client = MongoClient(cls.test_ini['host'], cls.test_ini['port'])

        # 接続確認
        try:
            cls.client.admin.command('hello')
            cls.db_server_connect = True
            print('Use DB.')
        except errors.ConnectionFailure:
            print('Do not use DB.')

        if cls.db_server_connect:
            # adminで認証
            cls.client = MongoClient(
                username=cls.test_ini['admin_user'],
                password=cls.test_ini['admin_password'])
            # DB作成
            cls.client[cls.test_ini['db']].command(
                "createUser",
                cls.test_ini['user'],
                pwd=cls.test_ini['password'],
                roles=[
                    {
                        'role': 'dbOwner',
                        'db': cls.test_ini['db'],
                    },
                ],
            )
            # edmanのDB接続オブジェクト作成
            con = {
                'host': cls.test_ini['host'],
                'port': cls.test_ini['port'],
                'user': cls.test_ini['user'],
                'password': cls.test_ini['password'],
                'database': cls.test_ini['db'],
                'options':[f"authSource={cls.test_ini['db']}"]
            }
            cls.db = DB(con)
            cls.testdb = cls.db.get_db

    @classmethod
    def tearDownClass(cls):
        if cls.db_server_connect:
            # cls.clientはpymongo経由でDB削除
            # cls.testdb.dbはedman側の接続オブジェクト経由でユーザ(自分自身)の削除
            cls.client.drop_database(cls.test_ini['db'])
            cls.testdb.command("dropUser", cls.test_ini['user'])

    def setUp(self):

        if self.db_server_connect:
            self.file = File(self.db.get_db)
        else:
            self.file = File()
        self.config = Config()

    # def tearDown(self):
    #     pass

    def test_file_gen(self):

        # 正常系
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)

            expected = []
            for i in range(2):
                gen_file = 'gen_test' + str(i) + '.txt'
                gen_path = p / gen_file
                with gen_path.open('w') as f:
                    test_var = 'test' + str(i)
                    expected.append((gen_file, test_var))
                    f.write(test_var)

            # ファイル読み込み、テスト
            actual = []
            files = tuple(sorted(p.glob('gen_test*.txt')))
            for idx, f in enumerate(self.file.file_gen(files)):
                filename, filedata = f
                actual.append((filename, filedata.decode()))
            self.assertListEqual(sorted(actual), sorted(expected))

    def test_add_file_reference(self):
        if not self.db_server_connect:
            return

        # refの場合
        # refデータ入力
        ref_json = {
            "structure_1": [
                {
                    "position": "top",
                    "username": "ryde",
                    "structure_2": [
                        {
                            "maker": "Ferrari",
                            "carname": "F355",
                            "power": 380,
                            "float_val": 4453.456
                        },
                        {
                            "maker": "HONDA",
                            "carname": "NSX",
                            "power": 280,
                            "float_val": 321.56,
                            "start_date": {"#date": "1981-04-23"},
                            "structure_3_1": [
                                {
                                    "filename": "test1.txt",
                                    "name": "添付ファイル1"
                                },
                                {
                                    "filename": "test2.txt",
                                    "name": "添付ファイル2"
                                }
                            ],
                            "structure_3_2": [
                                {
                                    "filename": "test3.txt",
                                    "name": "添付ファイル3",
                                    "structure_4": {
                                        "filename": "test4.txt",
                                        "name": "添付ファイル4",
                                        "structure_5": [
                                            {
                                                "url": "example2.com",
                                                "name": "テストURL2"
                                            },
                                            {
                                                "url": "example3.com",
                                                "name": "テストURL3"
                                            }
                                        ]
                                    },
                                    "structure_6": [
                                        {
                                            "url": "example_x.com",
                                            "name": "テストURL_x"
                                        },
                                        {
                                            "url": "example_y.com",
                                            "name": "テストURL_y"
                                        }
                                    ],
                                    "structure_5": {
                                        "url": "example.com",
                                        "name": "テストURL1",
                                        "structure_5": {
                                            "url": "example4.com",
                                            "name": "テストURL4"
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        convert = Convert()
        converted_edman = convert.dict_to_edman(ref_json, mode='ref')
        insert_result = self.db.insert(converted_edman)

        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)

            expected = []
            for i in range(2):
                gen_file = 'insert_file_ref_test' + str(i) + '.txt'
                gen_path = p / gen_file
                with gen_path.open('w') as f:
                    test_var = 'test' + str(i)
                    expected.append((gen_file, test_var))
                    f.write(test_var)

            file_path = tuple(sorted(p.glob('insert_file_ref_test*.txt')))

            # メソッド実行
            collection = 'structure_5'
            oid = [i[collection][0] for i in insert_result if collection in i][
                0]
            insert_file_result = self.file.add_file_reference(collection, oid,
                                                              file_path, 'ref',
                                                              compress=True)

            # DBからデータ取得
            query = {'_id': oid}
            result = self.testdb[collection].find_one(query)

            # 取得したデータからgridfsのファイルを取得
            actual = []
            self.fs = gridfs.GridFS(self.testdb)
            for file_oid in result[self.config.file]:
                data = self.fs.get(file_oid)
                d = data.read()
                if hasattr(data, 'compress') and data.compress == 'gzip':
                    d = gzip.decompress(d)
                actual.append((data.filename, d.decode()))

            # テスト
            self.assertTrue(insert_file_result)
            self.assertListEqual(sorted(actual), sorted(expected))

        # embの場合
        data = {
            "position": "top",
            "structure_2": [
                {
                    "maker": "Ferrari",
                    "carname": "F355",
                    "power": 380,
                    "float_val": 4453.456
                },
                {
                    "maker": "HONDA",
                    "carname": "NSX",
                    "power": 280,
                    "float_val": 321.56,
                    "structure_3_1": [
                        {
                            "filename": "test1.txt",
                            "name": "添付ファイル1"
                        },
                        {
                            "filename": "test2.txt",
                            "name": "添付ファイル2"
                        }
                    ],
                    "structure_3_2": [
                        {
                            "filename": "test3.txt",
                            "name": "添付ファイル3",
                            "structure_4": {
                                "filename": "test4.txt",
                                "name": "添付ファイル4",
                                "structure_5": [
                                    {
                                        "url": "example2.com",
                                        "name": "テストURL2"
                                    },
                                    {
                                        "url": "example3.com",
                                        "name": "テストURL3"
                                    }
                                ]
                            },
                            "structure_6": [
                                {
                                    "url": "example_x.com",
                                    "name": "テストURL_x"
                                },
                                {
                                    "url": "example_y.com",
                                    "name": "テストURL_y"
                                }
                            ],
                            "structure_5": {
                                "url": "example.com",
                                "name": "テストURL1",
                                "structure_5": {
                                    "url": "example4.com",
                                    "name": "テストURL4"
                                }
                            }
                        }
                    ]
                }
            ]
        }
        insert_result = self.testdb['structure_emb'].insert_one(data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)

            expected = []
            for i in range(2):
                gen_file = 'emb_test' + str(i) + '.txt'
                gen_path = p / gen_file
                with gen_path.open('w') as f:
                    test_var = 'test' + str(i)
                    f.write(test_var)
                    expected.append(test_var)
            files = tuple(sorted(p.glob('emb_test*.txt')))
            collection = 'structure_emb'
            oid = insert_result.inserted_id
            query = ['structure_2', '1']

            # メソッド実行
            insert_file_emb_result = self.file.add_file_reference(
                collection, oid, files, 'emb', query, compress=True)
            # ドキュメントをfindして出す
            result = self.testdb[collection].find_one({'_id': oid})

            # gridfsからデータ取得
            out_data = []
            self.fs = gridfs.GridFS(self.testdb)
            for oid in result['structure_2'][1][self.config.file]:
                data = self.fs.get(oid)
                f_data = data.read()
                if hasattr(data, 'compress') and data.compress == 'gzip':
                    f_data = gzip.decompress(f_data)

                out_data.append(f_data.decode())

            # DBデータとファイルのデータに差異はないか
            self.assertListEqual(sorted(expected), sorted(out_data))

            # メソッド成功時のフラグ
            self.assertTrue(insert_file_emb_result)

    def test_file_list_attachment(self):

        # _ed_fileがなかった場合
        doc = {'name': 'NSX', 'ddd': 'aaa'}
        files_oid = [ObjectId(), ObjectId()]
        actual = self.file.file_list_attachment(doc, files_oid)
        expected = {'name': 'NSX', 'ddd': 'aaa', self.config.file: files_oid}
        self.assertDictEqual(expected, actual)

        # _ed_fileがすでに存在する場合
        oid1 = ObjectId()
        oid2 = ObjectId()

        files_oid = [oid1, oid2]
        doc = {'abc': '123', self.config.file: files_oid}
        at_files_oid = [ObjectId(), ObjectId()]
        actual = self.file.file_list_attachment(doc, at_files_oid)

        files_oid2 = [oid1, oid2]
        expected = {'abc': '123', self.config.file: files_oid2 + at_files_oid}

        self.assertDictEqual(actual, expected)

    def test_file_list_replace(self):
        # _ed_fileがある場合
        files_oid = [ObjectId(), ObjectId()]
        doc = {'name': 'NSX', self.config.file: files_oid}
        rep_files_oid = [ObjectId(), ObjectId()]
        actual = self.file.file_list_replace(doc, rep_files_oid)
        expected = {'name': 'NSX', self.config.file: rep_files_oid}
        self.assertDictEqual(expected, actual)

        # 空リストの場合
        doc = {'name': 'NSX', self.config.file: [ObjectId(), ObjectId()]}
        rep_files_oid = []
        actual = self.file.file_list_replace(doc, rep_files_oid)
        expected = {'name': 'NSX'}
        self.assertDictEqual(expected, actual)

        # _ed_fileがない場合(例外になる)
        doc = {'name': 'NSX'}
        rep_files_oid = [ObjectId(), ObjectId()]
        with self.assertRaises(ValueError):
            _ = self.file.file_list_replace(doc, rep_files_oid)

    def test_fs_delete(self):
        if not self.db_server_connect:
            return

        # 正常系
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)

            for i in range(2):
                gen_file = 'delete_test' + str(i) + '.txt'
                gen_path = p / gen_file
                with gen_path.open('w') as f:
                    test_var = 'test' + str(i)
                    f.write(test_var)

            fs_oids = []
            for i in tuple(sorted(p.glob('delete_test*.txt'))):
                with i.open('rb') as f:
                    self.fs = gridfs.GridFS(self.testdb)
                    fs_oids.append(
                        self.fs.put(f.read(), filename=str(i.name)))

            self.file.fs_delete(fs_oids)
            for i in fs_oids:
                with self.subTest(i=i):
                    self.assertFalse(self.fs.exists(i))

    def test_download(self):
        if not self.db_server_connect:
            return

        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)
            test_vars = {}
            filename_list = []
            for i in range(2):
                name = 'file_dl' + str(i) + '.txt'
                filename_list.append(name)
                save_path = p / name
                with save_path.open('w') as f:
                    test_var = 'test' + str(i)
                    f.write(test_var)
                    test_vars.update({name: test_var})

            # ファイル読み込み、ファイルをgridfsに入れる
            files_oid = []
            self.fs = gridfs.GridFS(self.testdb)
            for filename in sorted(p.glob('file_dl*.txt')):
                with filename.open('rb') as f:
                    file_obj = gzip.compress(f.read(), compresslevel=6)
                    files_oid.append(
                        self.fs.put(file_obj, filename=filename.name,
                                    compress='gzip'))

            files_list_dic = dict(zip(files_oid, filename_list))

        with tempfile.TemporaryDirectory() as tmp_dl_dir:
            path = Path(tmp_dl_dir)

            # 正常テスト
            expected = {}
            for oid, file_name in files_list_dic.items():
                if self.file.download(oid, path):
                    if path.exists():
                        expected.update({oid: file_name})
            self.assertDictEqual(files_list_dic, expected)

            # files_list_dicファイルの中身が同じかテスト
            for name, txt in test_vars.items():
                dl_path = path / name
                with dl_path.open('rb') as f:
                    raw_data = f.read()
                    dl_data = raw_data.decode()
                    with self.subTest(name=name):
                        self.assertEqual(dl_data, txt)

    def test_get_file_names(self):
        if not self.db_server_connect:
            return

        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)
            filename_list = []
            for i in range(2):
                name = 'file_names' + str(i) + '.txt'
                filename_list.append(name)
                save_path = p / name
                with save_path.open('w') as f:
                    test_var = 'test' + str(i)
                    f.write(test_var)

            # ファイル読み込み、ファイルをgridfsに入れる
            files_oid = []
            self.fs = gridfs.GridFS(self.testdb)
            for filename in sorted(p.glob('file_names*.txt')):
                with filename.open('rb') as f:
                    files_oid.append(
                        self.fs.put(f.read(), filename=filename.name))

            # DocをDBに入れる
            doc = {
                'test1': {
                    'test2': 'name',
                    'test3': {
                        'test4': [
                            {
                                'test5': 'moon',
                                self.config.file: files_oid,
                            },
                            {'test6': 'star'}
                        ]
                    }
                }
            }
            insert_result = self.testdb['structure_emb'].insert_one(doc)

            # 正常系テスト(embのみ.refとembの判断はget_file_ref()で行っているので割愛)
            oid = insert_result.inserted_id
            query = ['test1', 'test3', 'test4', '0']
            actual = self.file.get_file_names('structure_emb', oid, 'emb',
                                              query)
            expected = dict(zip(files_oid, filename_list))
            self.assertDictEqual(actual, expected)

            # 正常系 ファイルがなかった場合 →空のリストを出力
            doc = {
                'test1': {
                    'test2': 'name2',
                    'test3': {
                        'test4': [
                            {'test5': 'moon2'},
                            {'test6': 'star2'}
                        ]
                    }
                }
            }
            insert_result = self.testdb['structure_ref'].insert_one(doc)
            oid = insert_result.inserted_id
            actual = self.file.get_file_names('structure_ref', oid, 'ref')
            self.assertDictEqual(actual, {})

            # 異常系
            # ドキュメントがなかった場合 →EdmanDbProcessErrorを補足
            oid = ObjectId()
            with self.assertRaises(EdmanDbProcessError):
                _ = self.file.get_file_names('structure_ref', oid, 'ref')

    def test__get_file_ref(self):
        # 正常系(ref)
        expected = [ObjectId(), ObjectId(), ObjectId()]
        doc = {
            'name': 'test1',
            self.config.file: expected,
            self.config.parent: DBRef('test0', ObjectId()),
            self.config.child: [DBRef('test2', ObjectId()),
                                DBRef('test3', ObjectId())]
        }
        structure = 'ref'
        actual = self.file.get_file_ref(doc, structure)
        self.assertListEqual(expected, actual)

        # 正常系(emb)
        expected = [ObjectId(), ObjectId(), ObjectId()]
        doc = {
            'test1': {
                'test2': 'name',
                'test3': {
                    'test4': [
                        {
                            'test5': 'moon',
                            self.config.file: expected,
                        },
                        {'test6': 'star'}
                    ]
                }
            }
        }
        structure = 'emb'
        query = ['test1', 'test3', 'test4', '0']
        actual = self.file.get_file_ref(doc, structure, query)
        self.assertListEqual(expected, actual)

    def test_delete(self):
        if not self.db_server_connect:
            return

        with tempfile.TemporaryDirectory() as tmp_dl_dir:
            p = Path(tmp_dl_dir)
            filename_list = []
            name = 'file_delete.txt'
            filename_list.append(name)
            save_path = p / name
            with save_path.open('w') as f:
                test_var = 'test'
                f.write(test_var)

            # embの添付ファイル削除テスト
            # ファイル読み込み、ファイルをgridfsに入れる
            files_oid = []
            self.fs = gridfs.GridFS(self.testdb)
            for filename in sorted(p.glob('file_delete*.txt')):
                with filename.open('rb') as f:
                    files_oid.append(
                        self.fs.put(f.read(), filename=filename.name))

            # DocをDBに入れる
            doc = {
                'test1': {
                    'test2': 'name',
                    'test3': {
                        'test4': [
                            {
                                'test5': 'moon',
                                self.config.file: files_oid,
                            },
                            {'test6': 'star'}
                        ]
                    }
                }
            }
            insert_result = self.testdb['structure_emb'].insert_one(doc)
            oid = str(insert_result.inserted_id)
            query = ['test1', 'test3', 'test4', '0']

            result = self.file.delete(files_oid[0], 'structure_emb', oid,
                                      'emb', query)
            self.assertTrue(result)
            # ファイルが消えたか検証
            self.assertFalse(self.fs.exists(files_oid[0]))

            # refの添付ファイル削除テスト
            # ファイル読み込み、ファイルをgridfsに入れる
            files_oid = []
            self.fs = gridfs.GridFS(self.testdb)
            for filename in sorted(p.glob('file_delete*.txt')):
                with filename.open('rb') as f:
                    files_oid.append(
                        self.fs.put(f.read(), filename=filename.name))

            # docをDBに入れる
            doc = {'name': 'test1',
                   self.config.file: files_oid,
                   self.config.parent: ObjectId(),
                   self.config.child: DBRef('child_col', ObjectId())}

            insert_result = self.testdb['structure_ref'].insert_one(doc)
            oid = str(insert_result.inserted_id)

            result = self.file.delete(files_oid[0], 'structure_ref', oid,
                                      'ref')
            self.assertTrue(result)
            # ファイルが消えたか検証
            self.assertFalse(self.fs.exists(files_oid[0]))

    def test__get_emb_files_list(self):

        # 正常系
        file_list = [ObjectId(), ObjectId()]

        doc = {
            "_id": ObjectId(),
            "position": "top",
            "username": "ryde",
            "bool": True,
            "structure_2": [
                {
                    "maker": "Ferrari",
                    "carname": "F355",
                    "power": 380,
                    "float_val": 4453.456
                },
                {
                    "maker": "HONDA",
                    "carname": "NSX",
                    "power": 280,
                    "float_val": 321.56,
                    "structure_3_1": [
                        {
                            "filename": "test1.txt",
                            "name": "添付ファイル1"
                        },
                        {
                            "filename": "test2.txt",
                            "name": "添付ファイル2"
                        }
                    ],
                    "structure_3_2": [
                        {
                            "filename": "test3.txt",
                            "name": "添付ファイル3",
                            "structure_4": {
                                "filename": "test4.txt",
                                "name": "添付ファイル4",
                                "structure_5": [
                                    {
                                        "url": "example2.com",
                                        "name": "テストURL2"
                                    },
                                    {
                                        "url": "example3.com",
                                        "name": "テストURL3"
                                    }
                                ]
                            },
                            "structure_6": [
                                {
                                    "url": "example_x.com",
                                    "name": "テストURL_x"
                                },
                                {
                                    "url": "example_y.com",
                                    "name": "テストURL_y",
                                    self.config.file: file_list,
                                }
                            ],
                            "structure_5": {
                                "url": "example.com",
                                "name": "テストURL1",
                                "structure_5": {
                                    "url": "example4.com",
                                    "name": "テストURL4"
                                }
                            }
                        }
                    ]
                }
            ]
        }

        query = ['structure_2', '1', 'structure_3_2', '0', 'structure_6', '1']
        actual = self.file._get_emb_files_list(doc, query)

        expected = file_list
        self.assertEqual(expected, actual)
