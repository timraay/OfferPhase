# Installation guide

## **Prerequisites**
- Git
- Python 3.8 or above
- A bot application on Discord's [developer portal](https://discord.com/developers/applications) with the Members priviliged gateway intent enabled

```
git clone https://github.com/timraay/OfferPhase.git
cd OfferPhase
pip install -r requirements.txt
```
Now copy the `config.template.yaml` file, name it `config.yaml`, and fill in any of the fields that have a `# TODO` comment.

Save the file once done, then run the bot:
```
python app.py
```
