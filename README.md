**WakatimeBlender** is a simple plugin for the [Blender](https://www.blender.org/) 3D graphics software that sends time-tracking statistics to the [Wakatime](https://wakatime.com) online service using official wakatime client.

### Installation

To install the plugin you need, in fact, only the [WakaTime.py](https://github.com/allista/WakatimeBlender/raw/master/WakaTime.py) file.
Download it somewhere, open the Blender, go to *File->User Preferences->Add-ons->Install from file*, then check the tick-box near the plugin name in the list to enable it. Finally, push *Save User Settings*.

![Installation](http://i.imgur.com/3ZtsKpb.png)

After that a dialog prompting to enter the WakaTime API key may appear. Enter your key here and push "OK". If the key is incorrect and an attempt to send statistics fails the dialog is shown again.

![Setup API Key dialog](http://i.imgur.com/2VDvtJ9.png)

If for some reason you wish to change the key, press Space to summon the floating menu, then start type "waka" until the "Enter WakaTime API Key" action is shown. Select that action to summon the dialog again.

![Setup API Key](http://i.imgur.com/if3PLTC.png)

When setup is finished, the plugin should start sending the time you've spent on the currently loaded .blend file automatically in the background. **Note**, that unless you save a newly created file no stats are gathered, because Wakatime needs a filepath.
