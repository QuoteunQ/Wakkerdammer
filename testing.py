class foo():
    def __init__(self, i):
        self.i = i

    def print_num(self):
        print(self.i)

    def add_method(self):
        def double_i(self):
            self.i *= 2
        self.double_i = double_i.__get__(self)

new_foo = foo(2)
new_foo.add_method()
new_foo.print_num()
new_foo.double_i()
new_foo.print_num()