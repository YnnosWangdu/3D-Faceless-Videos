Drop .ttf/.otf fonts here. ffmpeg uses them to burn captions, and you can point `"font"` in a storyboard at one for 3D text.

These free (OFL) fonts suit faceless videos and are available from fonts.google.com:
- **Montserrat Black**: the default caption family name.
- **Anton**: tall and condensed, punchy for titles.
- **Bebas Neue**: clean all-caps.
- **Poppins ExtraBold**: rounded and friendly.

Set `captions.font` to the font's family name. `fc-scan --format "%{family}\n" file.ttf` prints it.
