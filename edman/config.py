class Config:
    """
    このパッケージを利用したシステム上での共通の定義

    **デフォルトのままをおすすめする**

      | 定義を変更した場合、このパッケージを利用している他のシステムと、データ交換ができなくなる
      | DBにデータが入っている状態で、この定義を変更した場合、データが破壊される可能性が高い

    | それでも変更したい場合は、単一、もしくは同じシステム内で定義を統一すること
    | その場合、他のシステムとデータ交換したくなった場合は独自に変換スクリプトを作成すること
    """
    parent = '_ed_parent'  # 親のリファレンス情報
    child = '_ed_child'  # 子のリファレンス情報
    file = '_ed_file'  # Grid.fsのリファレンス情報
    date = '#date'  # 日付に変換する場合のタグ

    # Gzip 圧縮レベル (ファイル圧縮時に使用)
    gzip_compress_level = 6

    # 再帰で回数の上限に達した場合、下記を適切な値で設定
    # import sys
    # sys.setrecursionlimit(1000)  # pythonのデフォルトは1000
