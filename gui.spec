# -*- mode: python -*-
# pyinstaller gui.spec --onefile
# https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing
# if __name__ == '__main__':
#    # Pyinstaller fix
#    multiprocessing.freeze_support()  # http://bit.ly/2g4t1aL
#    main()

block_cipher = None


a = Analysis(['gui.py'],
             pathex=['C:\\Users\\Himel\\btsync\\Coding\\virtualenv\\projects\\umuc_trends\\echat'],
             binaries=None,
             datas=[('icon.ico', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='Echatr 1.0',
          debug=False,
          strip=False,
          upx=True,
          console=False, 
		  icon='icon.ico')
