import os
from dash_app import app

port = int(os.environ.get("PORT", 8503))
app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
