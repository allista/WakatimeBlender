**WakatimeBlender** is a simple plugin for the [Blender](https://www.blender.org/) 3D graphics software that sends time-tracking statistics to the [Wakatime](https://wakatime.com) online service using official wakatime client.

###Installation

To install the plugin you need, in fact, only the WakatimeBlender.py file. 
Download it somewhere, open the Blender, go to *File->User Preferences->Add-ons->Install from file*, then check the tick-box near the plugin name in the list to enable it. Finally, push *Save User Settings*.

![Installation](http://i.imgur.com/3ZtsKpb.png)

After that you will need to hit Space to open the floating menu and start to type "Waka" so that the entry "WakaTime API Key" is shown. Select it and enter your key.

![Setup API Key](http://i.imgur.com/if3PLTC.png)

![Setup API Key dialog](http://i.imgur.com/2VDvtJ9.png)

When setup is finished, the plugin should start sending the time you've spent on the currently loaded .blend file automatically in the background. **Note**, that unless you save a newly created file no stats are gathered, because Wakatime needs a filepath.
