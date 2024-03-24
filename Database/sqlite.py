import sqlite3


import sys
from pathlib import Path
# 現在のファイルの絶対パスを取得
current_file = Path(__file__).resolve()
current_directory = current_file.parent
# ルートディレクトリ（building）の絶対パスを取得
root_directory = current_directory.parent
# sys.pathにルートディレクトリを追加
sys.path.append(str(root_directory))
# ShopRecordクラスをインポート
from main import ShopRecord, QueryRecord



### ------------------- テーブルの初期作成 ------------------- ###

def create_user_table(DATABASE_PATH: str):
    """ Userテーブルを初期設定・作成（未作成の場合）

    Args:
        DATABASE_PATH (str): DBのパス
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # 下記項目でUserテーブルを定義して作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS User (
            id TEXT PRIMARY KEY
        )
    ''')

    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def create_shop_table(DATABASE_PATH: str):
    """ Shopテーブルを初期設定・作成（未作成の場合）

    Args:
        DATABASE_PATH (str): DBのパス
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # 下記項目でShopテーブルを定義して作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Shop (
            id TEXT PRIMARY KEY,
            name TEXT,
            img_url TEXT NOT NULL,
            access TEXT NOT NULL,
            affiliate_url TEXT NOT NULL,
            review_score INTEGER,
            review_quantity INTEGER
        )
    ''')

    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def create_search_table(DATABASE_PATH: str):
    """ Searchテーブル（UserとShopのリレーション）を初期設定・作成（未作成の場合）

    Args:
        DATABASE_PATH (str): DBのパス
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # 下記項目でSearchテーブルを定義して作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Search (
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            shop_id TEXT,
            UNIQUE (user_id, shop_id),
            FOREIGN KEY (user_id) REFERENCES User (id),
            FOREIGN KEY (shop_id) REFERENCES Shop (id)
        )
    ''')

    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def create_query_table(DATABASE_PATH: str):
    
    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Query (
            user_id TEXT,
            date TEXT,
            place TEXT,
            price INTEGER,
            freeword TEXT,
            PRIMARY KEY (user_id, date, place, price, freeword),
            FOREIGN KEY (user_id) REFERENCES User (id)
        )
    ''')
    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def setup_database(DATABASE_PATH: str) -> None:
    """ユーザーと店舗の情報・多対多の関係を記録したノミノミDBの作成。
    
    Args:
        DATABASE_PATH (str): DBのパス

    Returns:
       None:
    """ 

    # カーソルに身作成であれば、各テーブルを初期設定・作成
    create_user_table(DATABASE_PATH) # Userテーブル
    create_shop_table(DATABASE_PATH) # Shopテーブル

    create_search_table(DATABASE_PATH) # Searchテーブル　（User <-> Shop の中間テーブル）

    create_query_table(DATABASE_PATH) # Queryテーブル　（User -> Query の1対多テーブル）

    return None





### ------------------- Userテーブル、レコード ------------------- ###

def add_user_record(DATABASE_PATH: str, user_id: str) -> None:
    """ユーザーを追加

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID

    Returns:
        None:
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    cursor.execute('INSERT INTO User (id) VALUES (?)', (user_id,)) # レコードの追加
    connect.commit() # 反映させる

    # 接続をクローズ
    cursor.close()
    connect.close()

    return None

def is_new_user(DATABASE_PATH: str, user_id: str) -> bool:
    """新規ユーザーの場合True。
    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID

    Returns:
        bool:ユーザにとって初めての検索の場合はTrue。そうでなければFalseを返す。
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # ユーザーの検索条件を取得
    cursor.execute('SELECT 1 FROM User WHERE id = ?', (user_id,))

    # 新規ユーザーの場合
    if not cursor.fetchone(): # Noneの場合。
        connect.commit()

        # 接続をクローズ
        cursor.close()
        connect.close()

        return True
    
    # 登録済みのユーザーの場合
    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()

    return False # ['user1', '2023-01-01', 'Tokyo', 1000, 'Sample query 1']などの場合。


### ------------------- Queryテーブル、レコード ------------------- ###

def get_user_queries(DATABASE_PATH: str, user_id: str) -> list:
    """ユーザーの検索条件を取得

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID

    Returns:
        None:
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # ユーザーの検索条件を取得
    cursor.execute('SELECT * FROM Query WHERE user_id = ?', (user_id,))
    
    # ユーザーの検索条件
    user_queries = cursor.fetchone() # ['user1', '2023-01-01', 'Tokyo', 1000, 'Sample query 1']
    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()

    return user_queries


def add_empty_query_record(DATABASE_PATH: str, user_id: str) -> None:
    """新規ユーザーの検索条件レコードを内容を空の状態で登録する。

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID

    Returns:
        None:
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # user_id以外はNULLで登録
    cursor.execute('INSERT INTO Query (user_id, date, place, price, freeword) VALUES (?, NULL, NULL, NULL, NULL)', (user_id,))
    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def update_query(DATABASE_PATH: str, user_id: str, input_queries: list) -> None:
    """新規ユーザーの検索条件レコードを内容を空の状態で登録する。

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID
        new_user_queries (list): 新規に入力された検索条件 ['(clear)', '新橋', '', '海鮮 個室']

    Returns:
        None:
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # 前回の検索条件を取得
    cursor.execute('SELECT * FROM Query WHERE user_id = ?', (user_id,))
    previous_queries = cursor.fetchone()[1:5] # index:0 はキー(shop_id)のため。

    # 検索条件の更新
    updated_queries = [] # 更新後の検索条件 
    for previous_query, input_query in zip(previous_queries, input_queries):
        
        # 条件入力がない場合
        if not input_query:
            updated_queries.append(previous_query) # 前回の指定条件のまま
            continue
        
        # 条件クリアを意図した入力だった場合
        if input_query == '(clear)':
            updated_queries.append(None) # 「指定条件なし」に更新 修正・確認 DB側と型で齟齬がないか確認 jump
            continue
        
        # 新規条件指定の場合
        updated_queries.append(input_query) # 新条件を追加        

    # 検索条件を更新
    cursor.execute('UPDATE Query SET date = ?, place = ?, price = ?, freeword = ? WHERE user_id = ?', 
                   (updated_queries[0], updated_queries[1], updated_queries[2], updated_queries[3], user_id))

    connect.commit()
    
    # 接続をクローズ
    cursor.close()
    connect.close()


def get_query_record(DATABASE_PATH: str, user_id: str) -> QueryRecord:
    """ShopRecordインスタンスリストを作成

    Args:
        DATABASE_PATH (str): _description_
        user_id (str): _description_

    Returns:
        QueryRecord: _description_
    """
    # データベースに接続
    connect = sqlite3.connect(DATABASE_PATH)
    cursor = connect.cursor()

    # Shopテーブルから特定のshop_idの情報を取得
    cursor.execute('''
        SELECT date, place, price, freeword
        FROM Query
        WHERE user_id = ?
    ''', (user_id,))

    # 取得した情報をフェッチ
    fetched_query_record = cursor.fetchone()

    # 接続をクローズ
    cursor.close()
    connect.close()

    # 取得した情報を処理する（例えば、辞書などに変換する）
    query_record = QueryRecord()
    query_record.date = fetched_query_record[0]
    query_record.place = fetched_query_record[1]
    query_record.price = fetched_query_record[2]
    query_record.freeword = fetched_query_record[3]

    return query_record  # 取得した情報を返す




### ------------------- Shopテーブル、レコード ------------------- ###

def add_shop_record(DATABASE_PATH: str, shop_record) -> None:
    """Shopテーブルにレコードを追加

    Args:
        DATABASE_PATH (str): DBへのパス。
        shop_record (ShopRecord): ShopRecordインスタンス

    Returns:
        _type_: _description_
    """
    
    # 保存先のDBファイルをカーソル（操作対象）として扱う設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    cursor.execute(
        '''INSERT INTO Shop (
            id,
            name,
            img_url,
            access,
            affiliate_url,
            review_score,
            review_quantity
        ) VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (shop_record.shop_id, shop_record.name, shop_record.img_url, shop_record.access, shop_record.affiliate_url, shop_record.review_score, shop_record.review_quantity)
    ) # レコードの追加
    connect.commit() # 反映させる

    # 接続をクローズ
    cursor.close()
    connect.close()

    return None


def get_shop_record_list(DATABASE_PATH: str, shop_ids: list) -> list:
    """ShopRecordインスタンスリストを作成

    Args:
        DATABASE_PATH (str): _description_
        shop_ids (list): _description_

    Returns:
        list[ShopRecord]: _description_
    """
    # データベースに接続
    connect = sqlite3.connect(DATABASE_PATH)
    cursor = connect.cursor()

    try:
        dict_shop_record_list = []

        for shop_id in shop_ids: 
            # Shopテーブルから特定のshop_idの情報を取得
            cursor.execute('''
                SELECT id, name, img_url, access, affiliate_url, review_score, review_quantity
                FROM Shop
                WHERE id = ?
            ''', (shop_id,))

            # 取得した情報をフェッチ
            shop_record = cursor.fetchone()

            print(shop_record)

            # 取得した情報を処理する（例えば、辞書などに変換する）
            dict_shop_record_info = {
                'id': shop_record[0],
                'name': shop_record[1],
                'img_url': shop_record[2],
                'access': shop_record[3],
                'affiliate_url': shop_record[4],
                'review_score': shop_record[5],
                'review_quantity': shop_record[6]
            }

            dict_shop_record_list.append(dict_shop_record_info)

        return dict_shop_record_list  # 取得した情報を返す

    finally:
        # 接続をクローズ
        cursor.close()
        connect.close()


def extract_registered_shop_ids(DATABASE_PATH: str, shop_ids: list) -> list: # 修正　見返して何をする関数かわからない
    """shop_idリストのうち、Shopテーブルに登録済みのshop_idリストを抽出

    Args:
        DATABASE_PATH (str): DBのパス
        shop_ids (list): 元となるshop_idリスト

    Returns:
        list: DBに既に登録済みのshop_idリスト
    """

    # SQLiteへの接続
    connect = sqlite3.connect(DATABASE_PATH)
    cursor = connect.cursor()

    # Shopテーブルから指定されたshop_idsに存在しないレコードを取得
    cursor.execute('SELECT id FROM Shop WHERE id IN ({})'.format(','.join(['?'] * len(shop_ids))), shop_ids)
    registered_shop_ids = [row[0] for row in cursor.fetchall()]

    # 接続をクローズ
    cursor.close()
    connect.close()

    return registered_shop_ids


def fetch_shop_record(DATABASE_PATH: str, shop_id: str) -> ShopRecord:
    """DBに登録済みのShopレコードからShopRecordインスタンスを作成

    Args:
        DATABASE_PATH (str): _description_
        shop_id (str): _description_

    Returns:
        ShopRecord: _description_
    """
    connect = sqlite3.connect(DATABASE_PATH)
    cursor = connect.cursor()

    # shop_idに基づいてShopテーブルから情報を取得
    cursor.execute('SELECT * FROM Shop WHERE id = ?', (shop_id,))
    shop_record_infos = cursor.fetchone()

    # 念の為DBに未登録の場合のエラー処理
    if shop_record_infos == []:
        print("Shopテーブルからレコード情報を取得できませんでした。")
        return 

    # ShopRecordインスタンス作成
    shop_record = ShopRecord()
    # プロパティの更新
    shop_record.shop_id = shop_record_infos[0] # 既知だけど一応
    shop_record.name = shop_record_infos[1]
    shop_record.img_url = shop_record_infos[2]
    shop_record.access = shop_record_infos[3]
    shop_record.affiliate_url = shop_record_infos[4]
    shop_record.review_score = shop_record_infos[5]
    shop_record.review_quantity = shop_record_infos[6]

    # 接続終了
    connect.close()
    
    return shop_record


def upsert_shop_info(DATABASE_PATH: str, shop_id: str, shop_info: dict):
    """店舗レコード情報をDBにアップサート。
    "upsert" ：レコードが存在しない場合は新規に挿入し、既に存在する場合は更新する

    Args:
        DATABASE_PATH (str): データベースファイルのパス
        shop_id (str): 店舗のID
        shop_info (dict): 更新する店舗情報を含む辞書

    Returns:
        None
    """
    connect = sqlite3.connect(DATABASE_PATH)
    cursor = connect.cursor()

    # レコードが存在しない場合は新規挿入、既存の場合は更新する
    cursor.execute('INSERT OR REPLACE INTO Shop (id, name, img_url, access, affiliate_url, review_score, review_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (shop_id, shop_info['name'], shop_info['img_url'], shop_info['access'], shop_info['affiliate_url'], shop_info['review_score'], shop_info['review_quantity']))

    connect.commit()
    cursor.close()
    connect.close()


def shop_reputation(review_score: float) -> str:
    """店舗のreview_scoreに応じて評価(str)を返す

    Args:
        review_score (float): 3.0〜5.0 の、ユーザー評価(3.0以下はレビューなし扱いっぽい。)

    Returns:
        str: review_scoreでb分別される評価
    """

    if review_score < 4.0:
        return "Good!"
    elif review_score < 4.5:
        return "Very good!"
    else:
        return "Excellent!"
    

### ------------------- Searchテーブル、レコード ------------------- ###

def add_search_records(DATABASE_PATH: str, user_id: str, shop_ids: list) -> None:
    """UserとShopをつなぐ中間テーブルに、関係レコードを追加

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID
        shop_ids (list[str]): 店舗のHotpepper_IDのリスト
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # ヒットした各shop_idをSearchレコードとして追加
    for shop_id in shop_ids:
        cursor.execute('INSERT INTO Search (user_id, shop_id) VALUES (?, ?) ON CONFLICT(user_id, shop_id) DO NOTHING', (user_id, shop_id))
    
    # 反映させる
    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()

    return None


def get_user_shops(DATABASE_PATH: str, user_id: str) -> list:
    """ユーザーが持つshopのidを全て返す。

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーid

    Returns:
        list[str] : ユーザーが持つ全shop_idリスト。
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    cursor.execute('''
        SELECT Shop.name
        FROM Shop
        JOIN Search ON Shop.id = Search.shop_id
        WHERE Search.user_id = ?
    ''', (user_id,))

    user_shop_ids = [row[0] for row in cursor.fetchall()]

    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()

    return user_shop_ids


def delete_select_search_record(DATABASE_PATH: str, selected_search_record_ids: list) -> None:
    """指定された SearchレコードIDリスト に該当するレコードを削除する。

    Args:
        DATABASE_PATH (str): DBのパス
        selected_search_record_ids (list): 削除対象の Search レコードの ID を含むリスト

    Returns:
        None: 何も返さない
    """

    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # 削除対象の ID をカンマで結合して文字列を生成
    ids_string = ', '.join(map(str, selected_search_record_ids))

    # SQL クエリの実行
    cursor.execute(f'DELETE FROM Search WHERE id IN ({ids_string})')

    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def delete_all_search_records(DATABASE_PATH: str, user_id: str):
    """ユーザーの検索レコードを全削除する。

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのLINE_ID
    """
    # 保存先のDBファイルをカーソル（操作対象）として扱う設定設定
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    cursor.execute('DELETE FROM Search WHERE user_id = ?', (user_id,)) #　ユーザーのレコードを全削除
    connect.commit()

    # 接続をクローズ
    cursor.close()
    connect.close()


def select_shop(DATABASE_PATH: str, user_id: str, max_select_shop_quantity: int):
    """指定されたuser_idに関連するSearchレコードのidリストとshop_idのリストを取得します。

    Args:
        DATABASE_PATH (str): DBのパス
        user_id (str): ユーザーのID
        max_select_shop_quantity (int): 取得する最大のshop_idの数

    Returns:
        tuple: 選出したSearchレコードのidリスト, shop_idのリスト
    """
    
    connect = sqlite3.Connection(DATABASE_PATH)
    cursor = connect.cursor()

    # user_idが持つSearchレコードを全て取得
    cursor.execute('SELECT id, shop_id FROM Search WHERE user_id = ?', (user_id,))
    search_records = cursor.fetchall()

    # 最大数まで取得（max_select_shop_quantity以下の場合は全てを取得）
    selected_records = search_records[:max_select_shop_quantity]

    # IDリストと対応するshop_idリストを作成して返す
    selected_search_record_ids = [record[0] for record in selected_records]
    selected_shop_ids = [record[1] for record in selected_records]

    # 接続をクローズ
    cursor.close()
    connect.close()

    return selected_search_record_ids, selected_shop_ids


def has_search_record(DATABASE_PATH: str, user_id: str) -> bool:

    connect = sqlite3.connect(DATABASE_PATH)
    cursor = connect.cursor()

    # Searchテーブルからユーザーのレコードを検索
    cursor.execute('SELECT * FROM Search WHERE user_id = ?', (user_id,))
    search_records = cursor.fetchall()

    connect.close()

    # レコードが存在するかどうかを判定
    return bool(search_records)

