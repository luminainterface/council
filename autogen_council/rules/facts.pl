% Prolog Facts and Rules for Logical Reasoning
% ============================================

% Spatial Relations - Basic Facts
south(a, b).
south(b, c).
south(c, d).
north(x, y).
east(p, q).
west(q, r).
east(m, n).
west(n, o).

% Spatial Relations - Transitive Rules
south(X, Z) :- south(X, Y), south(Y, Z).
north(X, Z) :- north(X, Y), north(Y, Z).
east(X, Z) :- east(X, Y), east(Y, Z).
west(X, Z) :- west(X, Y), west(Y, Z).

% Spatial Relations - Opposite Relations
north(X, Y) :- south(Y, X).
south(X, Y) :- north(Y, X).
east(X, Y) :- west(Y, X).
west(X, Y) :- east(Y, X).

% Family Relations - Basic Facts
parent(john, mary).
parent(mary, alice).
parent(alice, bob).
parent(bob, charlie).
parent(susan, john).
parent(robert, mary).
parent(helen, alice).

% Family Relations - Derived Rules
grandparent(X, Z) :- parent(X, Y), parent(Y, Z).
greatgrandparent(X, Z) :- parent(X, Y), grandparent(Y, Z).
ancestor(X, Y) :- parent(X, Y).
ancestor(X, Z) :- parent(X, Y), ancestor(Y, Z).
sibling(X, Y) :- parent(Z, X), parent(Z, Y), X \= Y.
uncle(X, Y) :- parent(Z, Y), sibling(X, Z), male(X).
aunt(X, Y) :- parent(Z, Y), sibling(X, Z), female(X).

% Gender facts (for uncle/aunt rules)
male(john).
male(bob).
male(charlie).
male(robert).
female(mary).
female(alice).
female(susan).
female(helen).

% Temporal Relations - Basic Facts
before(morning, afternoon).
before(afternoon, evening).
before(evening, night).
before(monday, tuesday).
before(tuesday, wednesday).
before(wednesday, thursday).
before(thursday, friday).
before(friday, saturday).
before(saturday, sunday).

% Temporal Relations - Transitive Rules
before(X, Z) :- before(X, Y), before(Y, Z).
after(X, Y) :- before(Y, X).

% Causal Relations
causes(rain, wet_ground).
causes(wet_ground, slippery_road).
causes(slippery_road, accidents).
causes(X, Z) :- causes(X, Y), causes(Y, Z).

% Logical Operators
implies(X, Y) :- causes(X, Y).
equivalent(X, Y) :- implies(X, Y), implies(Y, X).

% Size/Distance Relations
bigger(elephant, mouse).
bigger(mouse, ant).
bigger(X, Z) :- bigger(X, Y), bigger(Y, Z).
smaller(X, Y) :- bigger(Y, X).

% Location Relations
in(paris, france).
in(london, england).
in(tokyo, japan).
in(france, europe).
in(england, europe).
in(japan, asia).
in(X, Z) :- in(X, Y), in(Y, Z).

% Academic Relations
teaches(prof_smith, mathematics).
teaches(prof_jones, physics).
teaches(prof_brown, chemistry).
studies(alice, mathematics).
studies(bob, physics).
studies(charlie, chemistry).
knows(X, Y) :- teaches(X, Z), studies(Y, Z).

% 3-hop reasoning examples built-in
% If A is south of B and B south of C, then A is south of C (handled by transitive rule)
% If John is parent of Mary and Mary is parent of Alice, then John is grandparent of Alice
% If morning is before afternoon and afternoon is before evening, then morning is before evening 