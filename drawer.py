def update_batches(self, obj, features=None):
    """
    Update draw batches for the given object
    features: List of features to update. If None, updates all features
    """
    if features:
        # Only clear and update specified features
        for feature in features:
            if feature in self.batches:
                del self.batches[feature]
        self._create_batches(obj, features)
    else:
        # Update all features
        self.batches.clear()
        self._create_batches(obj) 