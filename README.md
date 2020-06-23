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

### Configuration
The Add-On tries to "guess" the projects name from the current blend-filename or from the projects folder.

To fine-tune the project's name, there some options are available under *Preferences -> Add-ons -> WakaTime*.<br/>
(This is also the place where to enable the add-on.)

The first option decides, whether to use the directory-name for the project's name or the the filename (without the *.blend*-extensions) in WakaTime. 

With the project-name extracted, further processing takes place:
1. If there are specific (default: numbers, underscores and dots) **trailing** characters, those will be removed too.
2. Optional: add a prefix to the project's title.
3. Optional: add a postfix to the project's title.

#### Examples
1. To prevent any adjusting of the projects-name, remove all the characters from the text-field and press enter. Also remove any text from the pre- and postfix-strings.
2. To have the projects name have a ".blend"-extension, add ".blend" in the postfix-text-field.
3. To only remove trailing numbers (e.g. versions), enter "1234567890" in the trailing character-text-field and press enter.
4. To remove numbers, underscores and dots, enter "1234567890.\_" in the trailing character-text-field and press enter. (This is the default.)
5. To turn "captain_afterburner.blend" into the project-name "\[blender\] captain_afterburner", set the prefix to "\[blender\] ", the postfix to "" (nothing).
6. To turn "captain_afterburner_05.blend" into the project-name "\[blender\] captain_afterburner", apply steps #4 and #5 together.
7. If you want to use the "parent" directory's name, check "Use folder-name as project-name". All steps from #2 to #6 can still be used to adjust the name.