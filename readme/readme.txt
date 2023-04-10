Plugin for CudaText.
Snippets engine, which is described in CudaText wiki:
https://wiki.freepascal.org/CudaText_plugins#Snippets

Important notice:
For your own snippets it is better to create custom snippet package. Because if you modify
standard packages and reinstall them, your changes will be lost. That is why editing controls
are disabled for packages whose names start with "std." or "snippets."

Snippet folders (format of data is the same, VSCode JSON format):

1. CudaText snippets.
  These are packages with prefix "snippets_ct" in the Addons Manager.
  They are installed into folder [CudaText]/data/snippets_ct.
2. VSCode snippets.
  These are VSCode packages located in the VSCode repositories.
  They are installed to folder [CudaText]/data/snippets_vs.
  VSCode format support was big work done by @OlehL.
  
Authors:
  Alexey Torgashin (CudaText)
  Oleh Lutsak ( https://github.com/OlehL/ )
  Shovel ( https://github.com/halfbrained/ )
License: MIT
