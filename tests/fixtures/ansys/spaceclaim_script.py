clr.AddReference('SpaceClaim.Api.V25')
from SpaceClaim.Api.V25 import Model
from Window import ActiveWindow
block = Model.Box()
body = ActiveWindow.Selection
